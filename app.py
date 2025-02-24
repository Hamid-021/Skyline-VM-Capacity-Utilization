from flask import Flask, jsonify, request, Response
from flask_cors import CORS
from metrics_check import InstanceMetricsCollector
from datetime import datetime, timedelta
import csv
import io
import threading
import time

app = Flask(__name__)
CORS(app)
collector = InstanceMetricsCollector()

@app.route("/metrics", methods=["GET"])
def get_metrics():
    # Get latest metrics
    latest_metrics = collector.get_all_metrics()
    response = {
        "latest": True,
        "timestamp": datetime.now().isoformat(),
        "metrics": latest_metrics,
    }

    return jsonify(response)

@app.route("/metrics/<instance_uuid>", methods=["GET"])
def get_instance_metrics(instance_uuid):
    time_interval = request.args.get("timeInterval")

    if time_interval:
        try:
            # Parse the time interval (e.g., "30mins", "15mins", "5mins", "1min")
            if time_interval.endswith("mins"):
                minutes = int(time_interval[:-4])
            elif time_interval.endswith("min"):
                minutes = int(time_interval[:-3])
            else:
                return jsonify({"error": "Invalid time interval format. Use '30mins', '15mins', '5mins', or '1min'."}), 400

            # Calculate the start time based on the interval
            start_time = datetime.now() - timedelta(minutes=minutes)
            end_time = datetime.now()

            # Get historical metrics for the specified interval
            historical_metrics = collector.get_historical_metrics(instance_uuid, start_time, end_time)
            response = {
                "latest": False,
                "timestamp": datetime.now().isoformat(),
                "metrics": historical_metrics
            }
            return jsonify(response)
        except ValueError as e:
            return jsonify({"error": f"Invalid time interval format: {e}"}), 400
        except Exception as e:
            return jsonify({"error": str(e)}), 400

    # If no time interval is specified, return the latest metrics
    metrics = collector.get_all_metrics()
    instance_metrics = metrics.get(instance_uuid)

    if not instance_metrics:
        return jsonify({"error": "Instance not found"}), 404

    response = {
        "latest": True,
        "timestamp": datetime.now().isoformat(),
        "metrics": [instance_metrics]
    }

    return jsonify(response)

@app.route("/metrics/export/csv", methods=["GET"])
def export_csv():
    """
    API endpoint to export metrics for a specific instance as a CSV file.
    """
    instance_id = request.args.get("instance_id")
    if not instance_id:
        return jsonify({"error": "instance_id query parameter is required"}), 400

    # Get latest metrics
    metrics = collector.get_all_metrics()
    instance_metrics = metrics.get(instance_id)

    if not instance_metrics:
        return jsonify({"error": "Instance not found"}), 404

    # Prepare CSV data
    csv_data = "Timestamp,CPU Usage (%),Memory Usage (%),Network RX (MB),Network TX (MB)\n"
    timestamp = datetime.now().isoformat()
    cpu = instance_metrics["cpu"]["total_usage"]
    memory = instance_metrics["memory"]["memory_usage_percent"]
    network_rx = sum([iface["rx_bytes"] / (1024 * 1024) for iface in instance_metrics["network"]])
    network_tx = sum([iface["tx_bytes"] / (1024 * 1024) for iface in instance_metrics["network"]])
    csv_data += f"{timestamp},{cpu:.2f},{memory:.2f},{network_rx:.2f},{network_tx:.2f}\n"

    return Response(
        csv_data,
        mimetype="text/csv",
        headers={"Content-disposition": f"attachment; filename=metrics_export_{instance_id}.csv"},
    )

# Add this before app.run() in app.py
def collect_metrics_periodically():
    while True:
        collector.get_all_metrics()
        time.sleep(60)  # Collect every 60 seconds

thread = threading.Thread(target=collect_metrics_periodically, daemon=True)
thread.start()

if __name__ == "__main__":
    # Run Flask app
    app.run(host="0.0.0.0", port=8000, debug=True)
