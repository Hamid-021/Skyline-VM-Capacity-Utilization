import React, { useState, useEffect } from 'react';
import { Chart, Line, Point, Tooltip, Axis, Legend } from 'bizcharts';
import { Select, Spin, Card, Row, Col, Button, Modal } from 'antd';
import { get } from 'lodash';
import { FullscreenOutlined, ReloadOutlined } from '@ant-design/icons';

const { Option } = Select;

const timeRangeOptions = [
  { label: '1 Hour', value: '60mins' },
  { label: '30 Minutes', value: '30mins' },
  { label: '15 Minutes', value: '15mins' },
  { label: '5 Minutes', value: '5mins' },
  { label: '1 Minute', value: '1min' },
];

const Util = ({ detail = {} }) => {
  const [timeRange, setTimeRange] = useState('60mins');
  const [loading, setLoading] = useState(false);
  const [metricsData, setMetricsData] = useState([]);
  const [diskDevices, setDiskDevices] = useState([]);
  const [selectedDisk, setSelectedDisk] = useState('');
  const [fullscreenChart, setFullscreenChart] = useState(null);
  const [isModalVisible, setIsModalVisible] = useState(false);
  const instanceId = detail.id;

  const fetchMetrics = async () => {
    setLoading(true);
    try {
      const response = await fetch(
        `/api/metrics/${instanceId}?timeInterval=${timeRange}`
      );
      const data = await response.json();

      const newDiskDevices = data.metrics[0]?.disk?.map((d) => d.device) || [];
      setDiskDevices(newDiskDevices);

      if (newDiskDevices.length > 0 && !newDiskDevices.includes(selectedDisk)) {
        setSelectedDisk(newDiskDevices[0]);
      }

      const transformedData = [];
      data.metrics.forEach((metric) => {
        const timestamp = new Date(metric.timestamp);
        const cpuMetrics = get(metric, 'cpu.cpu_breakdown', {});
        const diskMetrics =
          metric.disk.find((d) => d.device === selectedDisk) || {};

        // Convert bytes to MB for Disk I/O (1 MB = 1e6 bytes)
        const diskReadMB = (diskMetrics.read_bytes || 0) / 1e6;
        const diskWriteMB = (diskMetrics.write_bytes || 0) / 1e6;

        // Convert bytes to KB for Network (1 KB = 1e3 bytes)
        const networkReceiveKB = metric.network.reduce(
          (sum, net) => sum + (net.rx_bytes || 0) / 1e3,
          0
        );
        const networkTransmitKB = metric.network.reduce(
          (sum, net) => sum + (net.tx_bytes || 0) / 1e3,
          0
        );

        transformedData.push(
          {
            timestamp,
            category: 'Idle',
            value: cpuMetrics.idle || 0,
            unit: '%',
          },
          {
            timestamp,
            category: 'IO Wait',
            value: cpuMetrics.iowait || 0,
            unit: '%',
          },
          {
            timestamp,
            category: 'System',
            value: cpuMetrics.system || 0,
            unit: '%',
          },
          {
            timestamp,
            category: 'User',
            value: cpuMetrics.user || 0,
            unit: '%',
          },
          {
            timestamp,
            category: 'Memory Used',
            value: metric.memory.used_memory_gb || 0,
            unit: 'GB',
          },
          {
            timestamp,
            category: 'Memory Free',
            value: metric.memory.available_memory_gb || 0,
            unit: 'GB',
          },
          {
            timestamp,
            category: 'Network Receive',
            value: networkReceiveKB,
            unit: 'KB',
          },
          {
            timestamp,
            category: 'Network Transmit',
            value: networkTransmitKB,
            unit: 'KB',
          },
          {
            timestamp,
            category: 'Disk Read',
            value: diskReadMB,
            unit: 'MB',
          },
          {
            timestamp,
            category: 'Disk Write',
            value: diskWriteMB,
            unit: 'MB',
          }
        );
      });

      setMetricsData(transformedData);
    } catch (error) {
      console.error('Error fetching metrics:', error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (instanceId) {
      fetchMetrics();
      const interval = setInterval(fetchMetrics, 60000);
      return () => clearInterval(interval);
    }
  }, [instanceId, timeRange, selectedDisk]);

  const commonChartProps = {
    padding: [30, 80, 60, 60],
    autoFit: true,
    height: 300,
    appendPadding: [10, 0, 0, 10],
    scale: {
      timestamp: {
        type: 'time',
        tickCount: timeRange === '1min' ? 3 : 5,
        mask: 'HH:mm',
      },
      value: {
        nice: true,
        tickCount: 5,
        min: 0,
        formatter: (val) => {
          if (val >= 1000) return `${(val / 1000).toFixed(0)}`;
          return val.toFixed(0);
        },
      },
    },
  };

  const timeAxisConfig = {
    label: {
      timestamp: {
        type: 'time',
        mask: 'HH:mm',
      },
      autoRotate: true,
      autoHide: false,
    },
  };

  const renderChart = (title, categories, chartType) => {
    const filteredData = metricsData.filter((d) =>
      categories.includes(d.category)
    );
    const unit = filteredData[0]?.unit || '';

    return (
      <Chart {...commonChartProps} data={filteredData}>
        <Tooltip
          shared
          showCrosshairs
          titleFormatter={(value) => {
            const date = new Date(value);
            return `${date.toLocaleTimeString('en-US', {
              hour: '2-digit',
              minute: '2-digit',
              hour12: false,
            })}`;
          }}
          formatter={(val) => ({
            name: val.category,
            value: `${val.value.toFixed(2)} ${val.unit}`,
          })}
        />
        <Axis
          name="value"
          label={{
            formatter: (val) => `${val} ${unit}`,
          }}
          offset={50}
        />
        <Axis name="timestamp" {...timeAxisConfig} />
        <Legend position="top-right" />
        <Line shape="smooth" position="timestamp*value" color="category" />
        <Point position="timestamp*value" color="category" />
      </Chart>
    );
  };

  const handleFullscreen = (chartType) => {
    setFullscreenChart(chartType);
    setIsModalVisible(true);
  };

  const renderChartHeader = (title, options = null, chartType) => (
    <div
      style={{
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
      }}
    >
      <span>{title}</span>
      <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
        {options}
        <FullscreenOutlined
          style={{ cursor: 'pointer' }}
          onClick={() => handleFullscreen(chartType)}
        />
      </div>
    </div>
  );

  return (
    <div className="instance-metrics">
      <div
        style={{
          marginBottom: 16,
          display: 'flex',
          justifyContent: 'flex-end',
          gap: '8px',
          alignItems: 'center',
        }}
      >
        <Button
          icon={<ReloadOutlined />}
          onClick={fetchMetrics}
          loading={loading}
        >
          Refresh
        </Button>
        <Select
          value={timeRange}
          onChange={setTimeRange}
          style={{ width: 120 }}
        >
          {timeRangeOptions.map((option) => (
            <Option key={option.value} value={option.value}>
              {option.label}
            </Option>
          ))}
        </Select>
      </div>

      <Spin spinning={loading}>
        <Row gutter={[16, 16]}>
          <Col span={12}>
            <Card
              id="chart-cpu"
              title={renderChartHeader('CPU Usage (%)', null, 'cpu')}
              bordered={false}
            >
              {renderChart(
                'CPU Usage',
                ['Idle', 'IO Wait', 'System', 'User'],
                'cpu'
              )}
            </Card>
          </Col>
          <Col span={12}>
            <Card
              id="chart-memory"
              title={renderChartHeader('Memory Usage (GB)', null, 'memory')}
              bordered={false}
            >
              {renderChart(
                'Memory Usage',
                ['Memory Used', 'Memory Free'],
                'memory'
              )}
            </Card>
          </Col>
          <Col span={12}>
            <Card
              id="chart-network"
              title={renderChartHeader(
                'Network Traffic (KiB)',
                null,
                'network'
              )}
              bordered={false}
            >
              {renderChart(
                'Network Traffic',
                ['Network Receive', 'Network Transmit'],
                'network'
              )}
            </Card>
          </Col>
          <Col span={12}>
            <Card
              id="chart-disk"
              title={renderChartHeader(
                'Disk I/O (MB)',
                <Select
                  value={selectedDisk}
                  onChange={setSelectedDisk}
                  style={{ width: 100 }}
                >
                  {diskDevices.map((device) => (
                    <Option key={device} value={device}>
                      {device}
                    </Option>
                  ))}
                </Select>,
                'disk'
              )}
              bordered={false}
            >
              {renderChart('Disk I/O', ['Disk Read', 'Disk Write'], 'disk')}
            </Card>
          </Col>
        </Row>
      </Spin>

      <Modal
        title="Chart View"
        visible={isModalVisible}
        onCancel={() => setIsModalVisible(false)}
        footer={null}
        width="90%"
        centered
        destroyOnClose
      >
        {fullscreenChart === 'cpu' &&
          renderChart(
            'CPU Usage',
            ['Idle', 'IO Wait', 'System', 'User'],
            'cpu'
          )}
        {fullscreenChart === 'memory' &&
          renderChart('Memory Usage', ['Memory Used', 'Memory Free'], 'memory')}
        {fullscreenChart === 'network' &&
          renderChart(
            'Network Traffic',
            ['Network Receive', 'Network Transmit'],
            'network'
          )}
        {fullscreenChart === 'disk' &&
          renderChart('Disk I/O', ['Disk Read', 'Disk Write'], 'disk')}
      </Modal>
    </div>
  );
};

export default Util;
