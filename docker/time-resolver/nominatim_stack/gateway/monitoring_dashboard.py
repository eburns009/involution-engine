#!/usr/bin/env python3
"""
System Monitoring Dashboard
==========================

Comprehensive monitoring dashboard that aggregates health status from:
1. Nominatim geocoding service
2. Time Resolver service
3. Integrated pipeline service
4. System resources and performance metrics

Provides both web interface and API endpoints for monitoring.
"""

import json
import logging
import requests
import psutil
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
import uvicorn

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuration
import os
NOMINATIM_URL = os.getenv("NOMINATIM_URL", "http://localhost:8080")
GEOCODING_SERVICE_URL = os.getenv("GEOCODING_SERVICE_URL", "http://localhost:8086")
TIME_RESOLVER_URL = os.getenv("TIME_RESOLVER_URL", "http://localhost:8082")
INTEGRATED_SERVICE_URL = os.getenv("INTEGRATED_SERVICE_URL", "http://localhost:8087")

app = FastAPI(
    title="System Monitoring Dashboard",
    description="Comprehensive monitoring for address-to-timezone pipeline",
    version="1.0.0"
)

# Data Models
class ServiceStatus(BaseModel):
    name: str
    url: str
    status: str  # healthy, degraded, unhealthy, unreachable
    response_time_ms: Optional[float] = None
    last_check: str
    details: Dict[str, Any] = {}
    error: Optional[str] = None

class SystemMetrics(BaseModel):
    timestamp: str
    cpu_usage_percent: float
    memory_usage_percent: float
    disk_usage_percent: float
    load_average: List[float]
    uptime_seconds: float

class MonitoringStatus(BaseModel):
    timestamp: str
    overall_status: str
    services: List[ServiceStatus]
    system_metrics: SystemMetrics
    alerts: List[str] = []

# Helper Functions
def check_service_health(name: str, url: str, endpoint: str = "/health", timeout: int = 10) -> ServiceStatus:
    """Check health of a service endpoint"""
    start_time = time.time()

    try:
        response = requests.get(f"{url}{endpoint}", timeout=timeout)
        response_time = (time.time() - start_time) * 1000

        if response.status_code == 200:
            try:
                data = response.json()
                return ServiceStatus(
                    name=name,
                    url=url,
                    status=data.get("status", "healthy"),
                    response_time_ms=response_time,
                    last_check=datetime.utcnow().isoformat(),
                    details=data
                )
            except json.JSONDecodeError:
                return ServiceStatus(
                    name=name,
                    url=url,
                    status="degraded",
                    response_time_ms=response_time,
                    last_check=datetime.utcnow().isoformat(),
                    details={"raw_response": response.text[:200]},
                    error="Invalid JSON response"
                )
        else:
            return ServiceStatus(
                name=name,
                url=url,
                status="unhealthy",
                response_time_ms=response_time,
                last_check=datetime.utcnow().isoformat(),
                error=f"HTTP {response.status_code}: {response.text[:200]}"
            )

    except requests.exceptions.Timeout:
        return ServiceStatus(
            name=name,
            url=url,
            status="unreachable",
            last_check=datetime.utcnow().isoformat(),
            error=f"Timeout after {timeout}s"
        )
    except requests.exceptions.ConnectionError:
        return ServiceStatus(
            name=name,
            url=url,
            status="unreachable",
            last_check=datetime.utcnow().isoformat(),
            error="Connection refused"
        )
    except Exception as e:
        return ServiceStatus(
            name=name,
            url=url,
            status="unreachable",
            last_check=datetime.utcnow().isoformat(),
            error=str(e)
        )

def get_system_metrics() -> SystemMetrics:
    """Collect system performance metrics"""
    try:
        cpu_usage = psutil.cpu_percent(interval=1)
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        load_avg = psutil.getloadavg() if hasattr(psutil, 'getloadavg') else [0, 0, 0]
        boot_time = psutil.boot_time()
        uptime = time.time() - boot_time

        return SystemMetrics(
            timestamp=datetime.utcnow().isoformat(),
            cpu_usage_percent=cpu_usage,
            memory_usage_percent=memory.percent,
            disk_usage_percent=disk.percent,
            load_average=list(load_avg),
            uptime_seconds=uptime
        )
    except Exception as e:
        logger.error(f"Failed to collect system metrics: {e}")
        return SystemMetrics(
            timestamp=datetime.utcnow().isoformat(),
            cpu_usage_percent=0,
            memory_usage_percent=0,
            disk_usage_percent=0,
            load_average=[0, 0, 0],
            uptime_seconds=0
        )

def check_nominatim_detailed() -> ServiceStatus:
    """Check Nominatim with detailed container health"""
    try:
        # Try to read the health status file we created in Phase 5
        import subprocess
        result = subprocess.run([
            "docker-compose", "exec", "-T", "nominatim",
            "cat", "/tmp/nominatim-health-status.json"
        ], capture_output=True, text=True, timeout=10)

        if result.returncode == 0:
            health_data = json.loads(result.stdout)
            return ServiceStatus(
                name="Nominatim (Detailed)",
                url=NOMINATIM_URL,
                status=health_data.get("overall_status", "unknown"),
                last_check=datetime.utcnow().isoformat(),
                details=health_data
            )
    except Exception as e:
        logger.warning(f"Could not read detailed Nominatim health: {e}")

    # Fallback to basic health check
    return check_service_health("Nominatim", NOMINATIM_URL, "/status.php")

def generate_alerts(services: List[ServiceStatus], metrics: SystemMetrics) -> List[str]:
    """Generate system alerts based on status and metrics"""
    alerts = []

    # Service alerts
    unhealthy_services = [s for s in services if s.status in ["unhealthy", "unreachable"]]
    if unhealthy_services:
        alerts.append(f"🚨 {len(unhealthy_services)} service(s) unhealthy: {', '.join([s.name for s in unhealthy_services])}")

    degraded_services = [s for s in services if s.status == "degraded"]
    if degraded_services:
        alerts.append(f"⚠️ {len(degraded_services)} service(s) degraded: {', '.join([s.name for s in degraded_services])}")

    # Performance alerts
    if metrics.cpu_usage_percent > 80:
        alerts.append(f"🔥 High CPU usage: {metrics.cpu_usage_percent:.1f}%")

    if metrics.memory_usage_percent > 85:
        alerts.append(f"💾 High memory usage: {metrics.memory_usage_percent:.1f}%")

    if metrics.disk_usage_percent > 90:
        alerts.append(f"💿 Critical disk usage: {metrics.disk_usage_percent:.1f}%")
    elif metrics.disk_usage_percent > 80:
        alerts.append(f"⚠️ High disk usage: {metrics.disk_usage_percent:.1f}%")

    # Response time alerts
    slow_services = [s for s in services if s.response_time_ms and s.response_time_ms > 5000]
    if slow_services:
        alerts.append(f"🐌 Slow response times: {', '.join([f'{s.name} ({s.response_time_ms:.0f}ms)' for s in slow_services])}")

    return alerts

# API Endpoints
@app.get("/health")
async def health_check():
    """Quick health check for the monitoring service itself"""
    return {"status": "healthy", "service": "monitoring_dashboard", "timestamp": datetime.utcnow().isoformat()}

@app.get("/status", response_model=MonitoringStatus)
async def get_full_status():
    """Get comprehensive system status"""
    services = [
        check_nominatim_detailed(),
        check_service_health("Geocoding Gateway", GEOCODING_SERVICE_URL),
        check_service_health("Time Resolver", TIME_RESOLVER_URL),
        check_service_health("Integrated Service", INTEGRATED_SERVICE_URL),
    ]

    metrics = get_system_metrics()
    alerts = generate_alerts(services, metrics)

    # Determine overall status
    if any(s.status in ["unhealthy", "unreachable"] for s in services):
        overall_status = "unhealthy"
    elif any(s.status == "degraded" for s in services) or len(alerts) > 0:
        overall_status = "degraded"
    else:
        overall_status = "healthy"

    return MonitoringStatus(
        timestamp=datetime.utcnow().isoformat(),
        overall_status=overall_status,
        services=services,
        system_metrics=metrics,
        alerts=alerts
    )

@app.get("/services")
async def get_services_status():
    """Get status of all services"""
    status = await get_full_status()
    return {"services": [s.dict() for s in status.services]}

@app.get("/metrics")
async def get_system_metrics_endpoint():
    """Get current system metrics"""
    return get_system_metrics().dict()

@app.get("/alerts")
async def get_current_alerts():
    """Get current system alerts"""
    status = await get_full_status()
    return {"alerts": status.alerts, "count": len(status.alerts)}

@app.get("/", response_class=HTMLResponse)
async def dashboard_html():
    """Web dashboard interface"""
    status = await get_full_status()

    # Simple HTML dashboard
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>System Monitoring Dashboard</title>
        <meta http-equiv="refresh" content="30">
        <style>
            body {{ font-family: Arial, sans-serif; margin: 20px; background: #f5f5f5; }}
            .container {{ max-width: 1200px; margin: 0 auto; }}
            .status-card {{ background: white; margin: 10px 0; padding: 15px; border-radius: 5px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
            .healthy {{ border-left: 5px solid #4CAF50; }}
            .degraded {{ border-left: 5px solid #FF9800; }}
            .unhealthy {{ border-left: 5px solid #F44336; }}
            .unreachable {{ border-left: 5px solid #9E9E9E; }}
            .alert {{ background: #ffebee; border: 1px solid #f44336; padding: 10px; margin: 5px 0; border-radius: 3px; }}
            .metrics {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 15px; }}
            .metric {{ text-align: center; }}
            h1 {{ color: #333; text-align: center; }}
            h2 {{ color: #666; margin-top: 30px; }}
            .timestamp {{ color: #888; font-size: 0.9em; }}
            .response-time {{ float: right; color: #666; font-size: 0.9em; }}
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🔍 System Monitoring Dashboard</h1>
            <p class="timestamp">Last updated: {status.timestamp} UTC | Auto-refresh: 30s</p>

            <div class="status-card {status.overall_status}">
                <h2>🎯 Overall Status: {status.overall_status.upper()}</h2>
            </div>

            {"".join([f'<div class="alert">🚨 {alert}</div>' for alert in status.alerts]) if status.alerts else ""}

            <h2>📊 System Metrics</h2>
            <div class="status-card">
                <div class="metrics">
                    <div class="metric">
                        <h3>💻 CPU Usage</h3>
                        <div style="font-size: 2em; color: {'#f44336' if status.system_metrics.cpu_usage_percent > 80 else '#4CAF50'}">{status.system_metrics.cpu_usage_percent:.1f}%</div>
                    </div>
                    <div class="metric">
                        <h3>💾 Memory Usage</h3>
                        <div style="font-size: 2em; color: {'#f44336' if status.system_metrics.memory_usage_percent > 85 else '#4CAF50'}">{status.system_metrics.memory_usage_percent:.1f}%</div>
                    </div>
                    <div class="metric">
                        <h3>💿 Disk Usage</h3>
                        <div style="font-size: 2em; color: {'#f44336' if status.system_metrics.disk_usage_percent > 90 else '#FF9800' if status.system_metrics.disk_usage_percent > 80 else '#4CAF50'}">{status.system_metrics.disk_usage_percent:.1f}%</div>
                    </div>
                    <div class="metric">
                        <h3>⏱️ Uptime</h3>
                        <div style="font-size: 1.5em; color: #4CAF50">{timedelta(seconds=int(status.system_metrics.uptime_seconds))}</div>
                    </div>
                </div>
            </div>

            <h2>🔧 Service Status</h2>
            {"".join([f'''
            <div class="status-card {service.status}">
                <h3>{service.name}
                    {f'<span class="response-time">{service.response_time_ms:.0f}ms</span>' if service.response_time_ms else ''}
                </h3>
                <p><strong>Status:</strong> {service.status.upper()}</p>
                <p><strong>URL:</strong> {service.url}</p>
                <p><strong>Last Check:</strong> {service.last_check}</p>
                {f'<p><strong>Error:</strong> {service.error}</p>' if service.error else ''}
                {f'<p><strong>Details:</strong> {len(service.details)} data points available</p>' if service.details else ''}
            </div>
            ''' for service in status.services])}

            <div class="status-card">
                <h3>📖 API Endpoints</h3>
                <ul>
                    <li><a href="/status">/status</a> - Full system status (JSON)</li>
                    <li><a href="/services">/services</a> - Services status only</li>
                    <li><a href="/metrics">/metrics</a> - System metrics only</li>
                    <li><a href="/alerts">/alerts</a> - Current alerts</li>
                    <li><a href="/health">/health</a> - Monitoring service health</li>
                </ul>
            </div>
        </div>
    </body>
    </html>
    """

    return HTMLResponse(content=html_content)

# Development server
if __name__ == "__main__":
    uvicorn.run(
        "monitoring_dashboard:app",
        host="0.0.0.0",
        port=8088,
        reload=True,
        log_level="info"
    )