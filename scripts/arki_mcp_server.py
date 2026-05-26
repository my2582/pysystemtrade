#!/usr/bin/env python3
"""
Arki Ops MCP Server (Model Context Protocol)
============================================
This is the foundational MCP server for Claude to interact with the
Arki pysystemtrade environment. It provides essential tools for daily operations
while strictly adhering to the "do not modify core pysystemtrade" rule.

Requirements:
    pip install mcp

Usage:
    Configure this script as an MCP server in Claude Desktop or your Claude client:
    "command": "/path/to/venv/bin/python",
    "args": ["/Users/msyeom/Developer/pysystemtrade/scripts/arki_mcp_server.py"]
"""

import sys
import subprocess
import json
from pathlib import Path
try:
    from mcp.server.fastmcp import FastMCP
except ImportError:
    print("Error: The 'mcp' package is not installed. Please run: pip install mcp")
    sys.exit(1)

# Initialize FastMCP Server
mcp = FastMCP("Arki-Ops-Server")

PROJECT_ROOT = Path("/Users/msyeom/Developer/pysystemtrade")
SCRIPTS_DIR = PROJECT_ROOT / "scripts"
RESULTS_DIR = PROJECT_ROOT / "results" / "runs"


def run_shell_command(cmd_list, timeout_sec=None):
    """Helper to run a shell command safely inside the project root."""
    try:
        result = subprocess.run(
            cmd_list,
            cwd=str(PROJECT_ROOT),
            capture_output=True,
            text=True,
            timeout=timeout_sec,
            check=False
        )
        output = result.stdout
        if result.stderr:
            output += f"\n--- STDERR ---\n{result.stderr}"
        return {
            "success": result.returncode == 0,
            "exit_code": result.returncode,
            "output": output
        }
    except subprocess.TimeoutExpired:
        return {"success": False, "error": f"Command timed out after {timeout_sec} seconds"}
    except Exception as e:
        return {"success": False, "error": str(e)}


@mcp.tool()
def update_prices() -> str:
    """
    Updates futures prices by fetching the latest data from Interactive Brokers.
    Fills all missing gaps automatically up to today.
    Prerequisite: IBKR Gateway/TWS must be running on 127.0.0.1:4001.
    """
    cmd = [sys.executable, str(SCRIPTS_DIR / "backfill_from_ib.py")]
    
    # This process can take several minutes, setting a long timeout.
    res = run_shell_command(cmd, timeout_sec=600)
    
    if res.get("success"):
        return f"Price update completed successfully.\nOutput:\n{res['output']}"
    else:
        return f"Price update failed (Code: {res.get('exit_code')}).\nError details:\n{res.get('output', res.get('error'))}"


@mcp.tool()
def run_backtest(config_yaml_path: str, label: str) -> str:
    """
    Runs a full production backtest using the specified configuration.
    
    Args:
        config_yaml_path: Relative path to the config (e.g., 'scripts/backtest_config/arki_production.yaml')
        label: A unique name for this backtest run (e.g., 'arki_prod_202605')
    """
    cmd = [
        sys.executable, 
        str(SCRIPTS_DIR / "backtest_runner.py"), 
        "full",
        "--label", label,
        "--mode", "dynamic",
        "--config", str(PROJECT_ROOT / config_yaml_path)
    ]
    
    res = run_shell_command(cmd, timeout_sec=900) # Dynamic backtests take ~8-10 mins
    
    if res.get("success"):
        return f"Backtest '{label}' completed successfully.\nLog:\n{res['output']}"
    else:
        return f"Backtest '{label}' failed.\nError details:\n{res.get('output', res.get('error'))}"


@mcp.tool()
def get_run_summary(label: str) -> str:
    """
    Retrieves the key performance metrics (Sharpe, CAGR, Drawdown, Executability)
    for a completed backtest run by reading its dashboard_meta.json file.
    
    Args:
        label: The name of the backtest run.
    """
    meta_path = RESULTS_DIR / label / "dashboard_meta.json"
    
    if not meta_path.exists():
        return f"Error: No dashboard metadata found for run '{label}' at {meta_path}."
    
    try:
        with open(meta_path, 'r') as f:
            data = json.load(f)
            
        stats = data.get("stats", {})
        executability = data.get("executability", {})
        
        summary = (
            f"Run: {label}\n"
            f"Capital: ${data.get('capital', 'N/A')}\n"
            f"Net Sharpe Ratio: {stats.get('sharpe', 'N/A')}\n"
            f"Gross Sharpe Ratio: {stats.get('gross_sharpe', 'N/A')}\n"
            f"CAGR: {stats.get('cagr', 'N/A')}%\n"
            f"Max Drawdown: {stats.get('max_drawdown', 'N/A')}%\n"
            f"Executability Score: {executability.get('score', 'N/A')}%"
        )
        return summary
    except Exception as e:
        return f"Failed to parse dashboard metadata: {str(e)}"


@mcp.tool()
def generate_dashboard(label: str) -> str:
    """
    Bundles the results of a backtest run into a standalone interactive HTML dashboard.
    
    Args:
        label: The name of the completed backtest run.
    """
    cmd = [
        sys.executable, 
        str(SCRIPTS_DIR / "bundle_dashboard.py"), 
        "--run", label
    ]
    
    res = run_shell_command(cmd, timeout_sec=60)
    
    if res.get("success"):
        # The script outputs the path to the HTML file in its standard output
        return f"Dashboard successfully generated for '{label}'.\n{res['output']}"
    else:
        return f"Failed to generate dashboard.\nError details:\n{res.get('output', res.get('error'))}"


@mcp.tool()
def optimize_universe(capital: float, target_count: int = 15) -> str:
    """
    Selects the optimal subset of instruments for a given capital size
    using Arki's 4-stage optimization pipeline (Quality, Executability, SR Scoring, Greedy Selection).
    
    Args:
        capital: The trading capital in USD (e.g., 200000).
        target_count: The desired number of instruments in the portfolio.
    """
    cmd = [
        sys.executable,
        str(SCRIPTS_DIR / "universe_optimizer.py"),
        "--capital", str(capital),
        "--target", str(target_count)
    ]
    res = run_shell_command(cmd, timeout_sec=120)
    if res.get("success"):
        return f"Universe Optimization Complete for ${capital}:\n{res['output']}"
    else:
        return f"Universe Optimization failed.\nError details:\n{res.get('output', res.get('error'))}"


@mcp.tool()
def run_strategy_audit(config_yaml_path: str) -> str:
    """
    Runs a structural audit on a given backtest configuration to check for errors,
    missing files, weighting issues, and executability problems before running a full backtest.
    
    Args:
        config_yaml_path: Relative path to the config (e.g., 'scripts/backtest_config/arki_production.yaml')
    """
    cmd = [
        sys.executable,
        str(SCRIPTS_DIR / "strategy_audit.py"),
        "--config", str(PROJECT_ROOT / config_yaml_path)
    ]
    res = run_shell_command(cmd, timeout_sec=60)
    if res.get("success"):
        return f"Strategy Audit Complete:\n{res['output']}"
    else:
        return f"Strategy Audit failed.\nError details:\n{res.get('output', res.get('error'))}"


@mcp.tool()
def generate_macro_data() -> str:
    """
    Generates combined Macro Mini and Multi-Factor dashboard data.
    Must be run whenever a new backtest universe is generated to update the Arki Macro dashboard tabs.
    """
    # 1. Run generate_arki_macro_data.py
    cmd1 = [sys.executable, str(SCRIPTS_DIR / "generate_arki_macro_data.py")]
    res1 = run_shell_command(cmd1, timeout_sec=60)
    
    # 2. Run generate_macro_universe_compare.py
    cmd2 = [sys.executable, str(SCRIPTS_DIR / "generate_macro_universe_compare.py")]
    res2 = run_shell_command(cmd2, timeout_sec=60)
    
    output = "=== Generate Arki Macro Data ===\n" + res1.get('output', '') + "\n"
    output += "=== Generate Macro Universe Compare ===\n" + res2.get('output', '')
    
    if res1.get("success") and res2.get("success"):
        return f"Macro dashboard data successfully updated.\n\n{output}"
    else:
        return f"Failed to update macro dashboard data.\n{output}"


if __name__ == "__main__":
    # Start the MCP server using standard I/O streams
    mcp.run(transport='stdio')
