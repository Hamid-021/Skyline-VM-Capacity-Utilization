import libvirt
import time
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import xml.etree.ElementTree as ET
import openstack

class InstanceMetricsCollector:
    def __init__(self):
        self.hypervisor_connections = {}
        self.cloud = openstack.connect()
        self.server_id_map = self._get_server_id_map()
        self.prev_cpu_stats = {}
        self.prev_disk_stats = {}
        self.prev_network_stats = {}
        self.metrics_history = {}  # To store historical metrics

        hypervisors = self.cloud.compute.hypervisors()
        if hypervisors:
            for hypervisor in hypervisors:
                hypervisor_details = self.cloud.compute.get_hypervisor(hypervisor.id)
                hypervisor_ip = hypervisor_details.host_ip
                uri = f"qemu+tcp://root@{hypervisor_ip}/system"
                try:
                    conn = libvirt.open(uri)
                    if conn is None:
                        raise Exception(f"Failed to open connection to {uri}")
                    self.hypervisor_connections[hypervisor_ip] = conn
                except libvirt.libvirtError as e:
                    print(f"Libvirt error connecting to {uri}: {e}")
                except Exception as e:
                    print(f"Error: {e}")
        else:
            print("No hypervisors found.")

    def _get_server_id_map(self) -> Dict[str, str]:
        servers = self.cloud.compute.servers()
        return {server.id: server.id for server in servers}

    def get_instance_names_and_ids(self, conn) -> List[Tuple[str, str]]:
        domain_ids = conn.listDomainsID()
        instances = []
        for dom_id in domain_ids:
            domain = conn.lookupByID(dom_id)
            instances.append((domain.name(), domain.UUIDString()))
        return instances

    def get_cpu_stats(self, conn, domain_name: str, instance_uuid: str) -> Optional[Dict]:
        try:
            domain = conn.lookupByName(domain_name)
            if not domain.isActive():
                return None

            cpu_stats = domain.getCPUStats(True)[0]
            vcpus = domain.maxVcpus()
            prev_stats = self.prev_cpu_stats.get(instance_uuid, {})
            current_time = time.time()
            time_delta = current_time - prev_stats.get('timestamp', current_time)

            # Calculate CPU usage deltas in nanoseconds
            total_delta = cpu_stats.get('cpu_time', 0) - prev_stats.get('cpu_time', 0)
            system_delta = cpu_stats.get('system_time', 0) - prev_stats.get('system_time', 0)
            user_delta = cpu_stats.get('user_time', 0) - prev_stats.get('user_time', 0)

            # Calculate maximum possible CPU time
            max_possible = vcpus * time_delta * 1e9  # Convert seconds to nanoseconds

            # Calculate percentages
            if max_possible > 0:
                total_usage = (total_delta / max_possible) * 100
                system_percent = (system_delta / max_possible) * 100
                user_percent = (user_delta / max_possible) * 100
                iowait_percent = ((total_delta - system_delta - user_delta) / max_possible) * 100
                idle_percent = max(0, 100 - (system_percent + user_percent + iowait_percent))
            else:
                total_usage = system_percent = user_percent = iowait_percent = 0
                idle_percent = 100

            # Update previous stats
            self.prev_cpu_stats[instance_uuid] = {
                'cpu_time': cpu_stats.get('cpu_time', 0),
                'system_time': cpu_stats.get('system_time', 0),
                'user_time': cpu_stats.get('user_time', 0),
                'timestamp': current_time
            }

            return {
                'cpu_breakdown': {
                    'idle': idle_percent,
                    'iowait': iowait_percent,
                    'system': system_percent,
                    'user': user_percent
                },
                'vcpus': vcpus,
                'total_usage': total_usage
            }
        except Exception as e:
            print(f"Error getting CPU stats: {str(e)}")
            return None

    def get_memory_stats(self, conn, domain_name: str) -> Optional[Dict]:
        try:
            domain = conn.lookupByName(domain_name)
            if not domain.isActive():
                return None

            memory_stats = domain.memoryStats()
            total_kb = memory_stats.get('actual', 0)
            available_kb = memory_stats.get('unused', 0)
            used_kb = total_kb - available_kb

            # Convert to GB
            total_gb = total_kb / (1024 ** 2)
            used_gb = used_kb / (1024 ** 2)
            available_gb = available_kb / (1024 ** 2)

            # Calculate usage percentage
            usage_percent = (used_kb / total_kb * 100) if total_kb > 0 else 0

            return {
                'total_memory_gb': total_gb,
                'used_memory_gb': used_gb,
                'available_memory_gb': available_gb,
                'memory_usage_percent': usage_percent
            }
        except Exception as e:
            print(f"Error getting memory stats: {str(e)}")
            return None

    def get_disk_stats(self, conn, domain_name: str) -> List[Dict]:
        disks = []
        try:
            domain = conn.lookupByName(domain_name)
            if not domain.isActive():
                return disks

            tree = ET.fromstring(domain.XMLDesc())
            for disk in tree.findall(".//disk"):
                if disk.get('device') == 'disk':
                    target = disk.find('target')
                    if target is not None:
                        dev = target.get('dev')
                        try:
                            stats = domain.blockStats(dev)
                            block_info = domain.blockInfo(dev)
                            allocation = block_info[0]  # Actual space used
                            capacity = block_info[1]    # Total available space

                            # Calculate actual used size and percentage
                            used_size = allocation
                            # Protect against division by zero and ensure percentage is between 0-100
                            usage_percent = min(100.0, (used_size / capacity * 100)) if capacity > 0 else 0.0

                            disks.append({
                                'device': dev,
                                'read_bytes': stats[0],
                                'write_bytes': stats[2],
                                'read_requests': stats[1],
                                'write_requests': stats[3],
                                'total_size': capacity,
                                'used_size': used_size,
                                'usage_percent': round(usage_percent, 2)  # Round to 2 decimal places
                            })
                        except libvirt.libvirtError as e:
                            print(f"Error getting disk stats for {dev}: {str(e)}")
        except Exception as e:
            print(f"Error getting disk stats: {str(e)}")
        return disks

    def get_network_stats(self, conn, domain_name: str) -> List[Dict]:
        interfaces = []
        try:
            domain = conn.lookupByName(domain_name)
            if not domain.isActive():
                return interfaces

            tree = ET.fromstring(domain.XMLDesc())
            for interface in tree.findall(".//interface"):
                target = interface.find('target')
                if target is not None:
                    dev = target.get('dev')
                    try:
                        stats = domain.interfaceStats(dev)
                        interfaces.append({
                            'interface': dev,
                            'rx_bytes': stats[0],
                            'tx_bytes': stats[4],
                            'rx_packets': stats[1],
                            'tx_packets': stats[5],
                            'rx_errors': stats[2],
                            'tx_errors': stats[6]
                        })
                    except libvirt.libvirtError as e:
                        print(f"Error getting network stats for {dev}: {str(e)}")
        except Exception as e:
            print(f"Error getting network stats: {str(e)}")
        return interfaces

    def get_all_metrics(self) -> Dict:
        metrics = {}
        for hypervisor_ip, conn in self.hypervisor_connections.items():
            instances = self.get_instance_names_and_ids(conn)
            for instance_name, instance_uuid in instances:
                try:
                    server_id = self.server_id_map.get(instance_uuid, "Unknown")
                    cpu_stats = self.get_cpu_stats(conn, instance_name, instance_uuid)
                    memory_stats = self.get_memory_stats(conn, instance_name)
                    disk_stats = self.get_disk_stats(conn, instance_name)
                    network_stats = self.get_network_stats(conn, instance_name)

                    instance_metrics = {
                        'instance_name': instance_name,
                        'server_id': server_id,
                        'timestamp': datetime.now().isoformat(),
                        'cpu': cpu_stats,
                        'memory': memory_stats,
                        'disk': disk_stats,
                        'network': network_stats
                    }

                    metrics[instance_uuid] = instance_metrics

                    # Store historical metrics
                    if instance_uuid not in self.metrics_history:
                        self.metrics_history[instance_uuid] = []
                    self.metrics_history[instance_uuid].append(instance_metrics)

                    # Keep only the last 60 minutes of data
                    self.metrics_history[instance_uuid] = [
                        m for m in self.metrics_history[instance_uuid]
                        if datetime.fromisoformat(m['timestamp']) > datetime.now() - timedelta(minutes=120)
                    ]
                except Exception as e:
                    print(f"Error collecting metrics for instance {instance_name} on hypervisor {hypervisor_ip}: {str(e)}")
                    continue
        return metrics

    def get_historical_metrics(self, instance_uuid: str, start_time: datetime, end_time: datetime) -> List[Dict]:
        if instance_uuid not in self.metrics_history:
            return []

        # Filter metrics based on the time range
        return [
            m for m in self.metrics_history[instance_uuid]
            if start_time <= datetime.fromisoformat(m['timestamp']) <= end_time
        ]

    def __del__(self):
        for conn in self.hypervisor_connections.values():
            try:
                conn.close()
            except:
                pass
