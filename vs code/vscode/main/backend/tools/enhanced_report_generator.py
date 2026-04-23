"""
Enhanced Automation Reporter with improved features:
- Step-level timing
- Retry tracking
- Better statistics
- Screenshot embedding
- Improved HTML styling
"""

import os
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict
from playwright.sync_api import sync_playwright


class AutomationReporter:
    """Enhanced automation reporter with comprehensive tracking"""

    def __init__(self, title="Automation Test Report"):
        self.title = title
        self.start_time = datetime.now()
        self.end_time = None
        self.status = "RUNNING"
        self.test_steps: List[Dict] = []
        self.logs: List[str] = []
        self.execution_time = 0
        self.screenshots: List[str] = []
        self.retry_count = 0

    # ------------------------------
    # Logging
    # ------------------------------
    def add_log(self, message: str) -> None:
        """Add a log message"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        log_entry = f"[{timestamp}] {message}"
        self.logs.append(log_entry)
        print(log_entry)

    def add_test_step(
        self, 
        name: str, 
        status: str, 
        duration: float = 0, 
        error: Optional[str] = None,
        screenshot: Optional[str] = None,
        retry_attempt: int = 0
    ) -> None:
        """
        Add a test step with timing and optional screenshot
        
        Args:
            name: Step name
            status: passed/failed/warning/skipped
            duration: Step execution time in seconds
            error: Error message if failed
            screenshot: Path to screenshot if captured
            retry_attempt: Retry attempt number (0 = first try)
        """
        step = {
            "name": name,
            "status": status,
            "duration": duration,
            "error": error,
            "timestamp": datetime.now().isoformat(),
            "screenshot": screenshot,
            "retry_attempt": retry_attempt
        }
        
        self.test_steps.append(step)
        
        # Track retries
        if retry_attempt > 0:
            self.retry_count += 1

    def add_screenshot(self, path: str) -> None:
        """Track a screenshot"""
        self.screenshots.append(path)

    def finalize(self, status: str, execution_time: float) -> None:
        """Finalize the report"""
        self.status = status.upper()
        self.execution_time = execution_time
        self.end_time = datetime.now()

    # ------------------------------
    # Statistics
    # ------------------------------
    def get_statistics(self) -> Dict:
        """Calculate comprehensive statistics"""
        total = len(self.test_steps)
        passed = len([s for s in self.test_steps if s["status"] == "passed"])
        failed = len([s for s in self.test_steps if s["status"] == "failed"])
        warning = len([s for s in self.test_steps if s["status"] == "warning"])
        skipped = len([s for s in self.test_steps if s["status"] == "skipped"])
        
        pass_rate = (passed / total * 100) if total > 0 else 0
        fail_rate = (failed / total * 100) if total > 0 else 0
        
        avg_duration = (
            sum(s["duration"] for s in self.test_steps) / total
            if total > 0 else 0
        )
        
        total_duration = sum(s["duration"] for s in self.test_steps)
        
        return {
            "total": total,
            "passed": passed,
            "failed": failed,
            "warning": warning,
            "skipped": skipped,
            "pass_rate": pass_rate,
            "fail_rate": fail_rate,
            "avg_duration": avg_duration,
            "total_duration": total_duration,
            "retry_count": self.retry_count
        }

    # ------------------------------
    # Generate HTML Report
    # ------------------------------
    def generate_html_report(self, output_path: str) -> str:
        """Generate enhanced HTML report"""
        
        stats = self.get_statistics()

        html = f"""
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{self.title}</title>
<style>
* {{
    margin: 0;
    padding: 0;
    box-sizing: border-box;
}}

body {{
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, sans-serif;
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    padding: 20px;
    line-height: 1.6;
}}

.container {{
    max-width: 1400px;
    margin: 0 auto;
    background: white;
    border-radius: 16px;
    box-shadow: 0 20px 60px rgba(0,0,0,0.3);
    overflow: hidden;
}}

.header {{
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    color: white;
    padding: 40px;
}}

.header h1 {{
    font-size: 2.5em;
    margin-bottom: 10px;
}}

.header-info {{
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
    gap: 20px;
    margin-top: 20px;
}}

.header-info-item {{
    background: rgba(255,255,255,0.1);
    padding: 15px;
    border-radius: 8px;
    backdrop-filter: blur(10px);
}}

.header-info-item strong {{
    display: block;
    font-size: 0.9em;
    opacity: 0.9;
    margin-bottom: 5px;
}}

.header-info-item span {{
    font-size: 1.3em;
    font-weight: 600;
}}

.content {{
    padding: 40px;
}}

.section {{
    margin-bottom: 40px;
}}

.section h2 {{
    font-size: 1.8em;
    color: #333;
    margin-bottom: 20px;
    padding-bottom: 10px;
    border-bottom: 3px solid #667eea;
}}

/* Statistics Cards */
.stats-grid {{
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
    gap: 20px;
    margin-bottom: 30px;
}}

.stat-card {{
    padding: 25px;
    border-radius: 12px;
    text-align: center;
    color: white;
    transition: transform 0.3s ease;
}}

.stat-card:hover {{
    transform: translateY(-5px);
}}

.stat-card h3 {{
    font-size: 2.5em;
    margin-bottom: 10px;
}}

.stat-card p {{
    font-size: 1em;
    opacity: 0.9;
}}

.stat-total {{ background: linear-gradient(135deg, #667eea, #764ba2); }}
.stat-passed {{ background: linear-gradient(135deg, #4CAF50, #45a049); }}
.stat-failed {{ background: linear-gradient(135deg, #f44336, #d32f2f); }}
.stat-warning {{ background: linear-gradient(135deg, #FF9800, #F57C00); }}
.stat-skipped {{ background: linear-gradient(135deg, #9E9E9E, #757575); }}
.stat-retry {{ background: linear-gradient(135deg, #2196F3, #1976D2); }}

/* Progress Bars */
.progress-section {{
    margin: 30px 0;
}}

.progress-bar {{
    height: 40px;
    background: #f0f0f0;
    border-radius: 20px;
    overflow: hidden;
    position: relative;
    margin-bottom: 20px;
}}

.progress-fill {{
    height: 100%;
    display: flex;
    align-items: center;
    justify-content: center;
    color: white;
    font-weight: bold;
    font-size: 1.1em;
    transition: width 1s ease;
}}

.progress-pass {{
    background: linear-gradient(90deg, #4CAF50, #45a049);
}}

.progress-fail {{
    background: linear-gradient(90deg, #f44336, #d32f2f);
}}

/* Test Steps */
.test-steps {{
    display: flex;
    flex-direction: column;
    gap: 15px;
}}

.test-step {{
    border-left: 5px solid #ccc;
    padding: 20px;
    background: #f9f9f9;
    border-radius: 8px;
    transition: all 0.3s ease;
}}

.test-step:hover {{
    box-shadow: 0 4px 12px rgba(0,0,0,0.1);
    transform: translateX(5px);
}}

.test-step.passed {{ border-left-color: #4CAF50; background: #f1f8f4; }}
.test-step.failed {{ border-left-color: #f44336; background: #fef5f5; }}
.test-step.warning {{ border-left-color: #FF9800; background: #fff8f0; }}
.test-step.skipped {{ border-left-color: #9E9E9E; background: #f5f5f5; }}

.step-header {{
    display: flex;
    justify-content: space-between;
    align-items: center;
    flex-wrap: wrap;
    gap: 10px;
    margin-bottom: 10px;
}}

.step-name {{
    font-size: 1.2em;
    font-weight: 600;
    color: #333;
}}

.step-badge {{
    padding: 6px 16px;
    border-radius: 20px;
    font-size: 0.85em;
    font-weight: bold;
    color: white;
    text-transform: uppercase;
}}

.step-badge.passed {{ background: #4CAF50; }}
.step-badge.failed {{ background: #f44336; }}
.step-badge.warning {{ background: #FF9800; }}
.step-badge.skipped {{ background: #9E9E9E; }}

.step-meta {{
    display: flex;
    gap: 20px;
    flex-wrap: wrap;
    color: #666;
    font-size: 0.9em;
    margin-top: 10px;
}}

.step-meta-item {{
    display: flex;
    align-items: center;
    gap: 5px;
}}

.step-meta-item strong {{
    color: #333;
}}

.step-error {{
    background: #ffebee;
    border: 1px solid #ffcdd2;
    padding: 15px;
    margin-top: 15px;
    border-radius: 8px;
    font-family: 'Courier New', monospace;
    color: #c62828;
    white-space: pre-wrap;
    word-break: break-word;
}}

.step-screenshot {{
    margin-top: 15px;
}}

.step-screenshot img {{
    max-width: 100%;
    border-radius: 8px;
    border: 2px solid #ddd;
    cursor: pointer;
    transition: transform 0.3s ease;
}}

.step-screenshot img:hover {{
    transform: scale(1.02);
}}

/* Metrics */
.metrics-grid {{
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
    gap: 20px;
    margin-top: 20px;
}}

.metric-card {{
    background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%);
    padding: 25px;
    border-radius: 12px;
    box-shadow: 0 4px 6px rgba(0,0,0,0.1);
}}

.metric-card h4 {{
    color: #555;
    font-size: 0.9em;
    margin-bottom: 10px;
    text-transform: uppercase;
}}

.metric-card .value {{
    font-size: 2em;
    font-weight: bold;
    color: #333;
}}

.metric-card .unit {{
    font-size: 0.9em;
    color: #666;
    margin-left: 5px;
}}

/* Status Badge */
.status-badge {{
    display: inline-block;
    padding: 10px 20px;
    border-radius: 25px;
    font-weight: bold;
    font-size: 1.2em;
    color: white;
}}

.status-badge.PASSED {{ background: #4CAF50; }}
.status-badge.FAILED {{ background: #f44336; }}
.status-badge.RUNNING {{ background: #2196F3; }}

/* Logs */
.logs-container {{
    background: #1e1e1e;
    color: #d4d4d4;
    padding: 20px;
    border-radius: 8px;
    font-family: 'Courier New', monospace;
    font-size: 0.9em;
    max-height: 400px;
    overflow-y: auto;
}}

.log-entry {{
    padding: 5px 0;
    border-bottom: 1px solid #333;
}}

.log-entry:last-child {{
    border-bottom: none;
}}

/* Responsive */
@media (max-width: 768px) {{
    .container {{
        border-radius: 0;
    }}
    
    .header, .content {{
        padding: 20px;
    }}
    
    .header h1 {{
        font-size: 1.8em;
    }}
    
    .stats-grid {{
        grid-template-columns: repeat(2, 1fr);
    }}
}}

@media print {{
    body {{
        background: white;
        padding: 0;
    }}
    
    .container {{
        box-shadow: none;
    }}
    
    .test-step {{
        page-break-inside: avoid;
    }}
}}
</style>
</head>
<body>
<div class="container">

<!-- Header -->
<div class="header">
    <h1>{self.title}</h1>
    <span class="status-badge {self.status}">{self.status}</span>
    
    <div class="header-info">
        <div class="header-info-item">
            <strong>Generated</strong>
            <span>{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}</span>
        </div>
        <div class="header-info-item">
            <strong>Duration</strong>
            <span>{self.execution_time:.2f}s</span>
        </div>
        <div class="header-info-item">
            <strong>Start Time</strong>
            <span>{self.start_time.strftime("%H:%M:%S")}</span>
        </div>
        <div class="header-info-item">
            <strong>End Time</strong>
            <span>{self.end_time.strftime("%H:%M:%S") if self.end_time else "N/A"}</span>
        </div>
    </div>
</div>

<!-- Content -->
<div class="content">

<!-- Summary Statistics -->
<div class="section">
    <h2>Summary</h2>
    <div class="stats-grid">
        <div class="stat-card stat-total">
            <h3>{stats['total']}</h3>
            <p>Total Steps</p>
        </div>
        <div class="stat-card stat-passed">
            <h3>{stats['passed']}</h3>
            <p>Passed</p>
        </div>
        <div class="stat-card stat-failed">
            <h3>{stats['failed']}</h3>
            <p>Failed</p>
        </div>
        <div class="stat-card stat-warning">
            <h3>{stats['warning']}</h3>
            <p>Warnings</p>
        </div>
        <div class="stat-card stat-skipped">
            <h3>{stats['skipped']}</h3>
            <p>Skipped</p>
        </div>
        <div class="stat-card stat-retry">
            <h3>{stats['retry_count']}</h3>
            <p>Retries</p>
        </div>
    </div>
</div>

<!-- Progress -->
<div class="section progress-section">
    <h2>Pass Rate</h2>
    <div class="progress-bar">
        <div class="progress-fill progress-pass" style="width:{stats['pass_rate']:.1f}%">
            {stats['pass_rate']:.1f}% Pass Rate
        </div>
    </div>
    
    {f'''<div class="progress-bar">
        <div class="progress-fill progress-fail" style="width:{stats['fail_rate']:.1f}%">
            {stats['fail_rate']:.1f}% Fail Rate
        </div>
    </div>''' if stats['fail_rate'] > 0 else ''}
</div>

<!-- Metrics -->
<div class="section">
    <h2>Performance Metrics</h2>
    <div class="metrics-grid">
        <div class="metric-card">
            <h4>Average Step Duration</h4>
            <div class="value">{stats['avg_duration']:.2f}<span class="unit">sec</span></div>
        </div>
        <div class="metric-card">
            <h4>Total Step Time</h4>
            <div class="value">{stats['total_duration']:.2f}<span class="unit">sec</span></div>
        </div>
        <div class="metric-card">
            <h4>Overhead Time</h4>
            <div class="value">{max(0, self.execution_time - stats['total_duration']):.2f}<span class="unit">sec</span></div>
        </div>
    </div>
</div>

<!-- Test Steps -->
<div class="section">
    <h2>Test Steps</h2>
    <div class="test-steps">
"""

        # Add each test step
        for i, step in enumerate(self.test_steps, 1):
            retry_badge = f" (Retry #{step['retry_attempt']})" if step['retry_attempt'] > 0 else ""
            
            html += f"""
        <div class="test-step {step['status']}">
            <div class="step-header">
                <div class="step-name">
                    {i}. {step['name']}{retry_badge}
                </div>
                <span class="step-badge {step['status']}">{step['status']}</span>
            </div>
            
            <div class="step-meta">
                <div class="step-meta-item">
                    <strong>Duration:</strong> {step['duration']:.2f}s
                </div>
                <div class="step-meta-item">
                    <strong>Time:</strong> {datetime.fromisoformat(step['timestamp']).strftime('%H:%M:%S')}
                </div>
            </div>
"""
            
            if step['error']:
                html += f"""
            <div class="step-error">{step['error']}</div>
"""
            
            if step.get('screenshot'):
                html += f"""
            <div class="step-screenshot">
                <img src="{step['screenshot']}" alt="Screenshot" onclick="window.open(this.src)">
            </div>
"""
            
            html += """
        </div>
"""

        html += """
    </div>
</div>
"""

        # Add logs if any
        if self.logs:
            html += """
<div class="section">
    <h2>Execution Logs</h2>
    <div class="logs-container">
"""
            for log in self.logs:
                html += f"""
        <div class="log-entry">{log}</div>
"""
            html += """
    </div>
</div>
"""

        html += """
</div> <!-- content -->
</div> <!-- container -->
</body>
</html>
"""

        # Write HTML file
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(html)

        return output_path

    # ------------------------------
    # Generate PDF Report
    # ------------------------------
    def generate_pdf_report(self, html_path: str, pdf_path: str) -> str:
        """Generate PDF from HTML report"""
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                page = browser.new_page()
                page.goto(f"file://{os.path.abspath(html_path)}")
                page.pdf(
                    path=pdf_path,
                    format="A4",
                    print_background=True,
                    margin={
                        "top": "1cm",
                        "right": "1cm",
                        "bottom": "1cm",
                        "left": "1cm"
                    }
                )
                browser.close()
            return pdf_path
        except Exception as e:
            print(f"Failed to generate PDF: {e}")
            return None

    # ------------------------------
    # Generate Both Reports
    # ------------------------------
    def generate_reports(self, report_dir: str) -> tuple:
        """Generate both HTML and PDF reports"""
        os.makedirs(report_dir, exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        html_path = os.path.join(report_dir, f"report_{timestamp}.html")
        pdf_path = os.path.join(report_dir, f"report_{timestamp}.pdf")

        # Generate HTML
        self.generate_html_report(html_path)
        
        # Generate PDF
        pdf_result = self.generate_pdf_report(html_path, pdf_path)
        
        return html_path, pdf_result or pdf_path