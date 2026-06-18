"""
Custom analytics module for Mycelium farm data analysis.

Provides helper functions, database connections, and visualization templates
for Jupyter notebook analytics environment.

Usage:
    from mycelium_analytics import *
    
    # Get recent harvest data
    df = get_production_summary(30)
    
    # Create yield trend visualization
    fig = plot_yield_trend(90)
    fig.show()
"""

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import sqlite3
import numpy as np
from datetime import datetime, timedelta
import os
from pathlib import Path

# Database configuration
_BASE_DIR = Path(__file__).parent
DB_PATHS = [
    str(_BASE_DIR / "storage" / "mycelium.db"),
    str(_BASE_DIR / "data" / "mycelium.db"),
    "./storage/mycelium.db",
    "./data/mycelium.db"
]

def get_connection():
    """
    Get database connection with row factory for easier data access.
    
    Returns:
        sqlite3.Connection: Database connection
    """
    for db_path in DB_PATHS:
        if os.path.exists(db_path):
            conn = sqlite3.connect(db_path)
            conn.row_factory = sqlite3.Row
            return conn
    
    # Fallback - try to find any .db file
    for db_file in Path(".").rglob("*.db"):
        if "mycelium" in str(db_file).lower():
            conn = sqlite3.connect(str(db_file))
            conn.row_factory = sqlite3.Row
            return conn
    
    raise FileNotFoundError("Could not locate Mycelium database file")

def query_to_df(query, params=None):
    """
    Execute query and return pandas DataFrame.
    
    Args:
        query (str): SQL query string
        params (dict, optional): Query parameters
        
    Returns:
        pd.DataFrame: Query results as DataFrame
    """
    try:
        with get_connection() as conn:
            return pd.read_sql_query(query, conn, params=params or {})
    except Exception as e:
        print(f"Query failed: {e}")
        print(f"Query: {query}")
        return pd.DataFrame()

def get_table_info(table_name):
    """
    Get column information for a specific table.
    
    Args:
        table_name (str): Name of the table
        
    Returns:
        pd.DataFrame: Table schema information
    """
    query = f"PRAGMA table_info({table_name})"
    return query_to_df(query)

def list_tables():
    """
    List all available tables in the database.
    
    Returns:
        list: Table names
    """
    query = "SELECT name FROM sqlite_master WHERE type='table'"
    df = query_to_df(query)
    return df['name'].tolist() if not df.empty else []

def get_production_summary(days=30):
    """
    Get production summary for specified period.
    
    Args:
        days (int): Number of days to look back
        
    Returns:
        pd.DataFrame: Production summary data
    """
    query = """
    SELECT DATE(harvest_ts) as date, 
           SUM(trimmed_wt) as daily_yield,
           COUNT(*) as harvest_count,
           AVG(trimmed_wt) as avg_harvest_weight
    FROM harvest 
    WHERE harvest_ts >= date('now', '-{} days')
    GROUP BY DATE(harvest_ts)
    ORDER BY date
    """.format(days)
    return query_to_df(query)

def get_environmental_data(days=7, device_type='spore'):
    """
    Get environmental sensor data.
    
    Args:
        days (int): Number of days to look back
        device_type (str): Type of device ('spore', 'hyphae', 'weather')
        
    Returns:
        pd.DataFrame: Environmental data
    """
    table_name = f"readings_{device_type}"
    query = f"""
    SELECT reading_ts, temperature, humidity, 
           device_id, room_id
    FROM {table_name}
    WHERE reading_ts >= date('now', '-{days} days')
    ORDER BY reading_ts
    """
    return query_to_df(query)

def get_harvest_with_environment(days=90):
    """
    Get harvest data joined with environmental conditions.
    
    Args:
        days (int): Number of days to look back
        
    Returns:
        pd.DataFrame: Harvest data with environmental correlations
    """
    query = """
    SELECT h.harvest_ts, h.total_wt, h.trimmed_wt,
           h.room_id, gr.room_name,
           AVG(rs.temperature) as avg_temp,
           AVG(rs.humidity) as avg_humidity,
           s.start_ts as spawn_start,
           julianday(h.harvest_ts) - julianday(s.start_ts) as cycle_days
    FROM harvest h
    JOIN grow_rooms gr ON h.room_id = gr.room_id
    LEFT JOIN bulk b ON h.bulk_id = b.bulk_id
    LEFT JOIN spawn s ON b.spawn_id = s.spawn_id
    LEFT JOIN readings_spore rs ON (h.room_id = rs.room_id 
                                   AND rs.reading_ts BETWEEN 
                                   date(h.harvest_ts, '-7 days') 
                                   AND h.harvest_ts)
    WHERE h.harvest_ts >= date('now', '-{} days')
    GROUP BY h.harvest_id
    ORDER BY h.harvest_ts DESC
    """.format(days)
    return query_to_df(query)

def get_financial_summary(months=12):
    """
    Get financial performance summary.
    
    Args:
        months (int): Number of months to look back
        
    Returns:
        pd.DataFrame: Financial summary data
    """
    query = """
    SELECT strftime('%Y-%m', st.transaction_ts) as month,
           SUM(sd.quantity * sd.unit_price) as revenue,
           COUNT(DISTINCT st.transaction_id) as transactions,
           AVG(sd.quantity * sd.unit_price) as avg_transaction
    FROM sales_transaction st
    JOIN sales_detail sd ON st.transaction_id = sd.transaction_id
    WHERE st.transaction_ts >= date('now', '-{} months')
    GROUP BY strftime('%Y-%m', st.transaction_ts)
    ORDER BY month DESC
    """.format(months)
    return query_to_df(query)

def get_labor_productivity(days=30):
    """
    Get labor productivity metrics.
    
    Args:
        days (int): Number of days to look back
        
    Returns:
        pd.DataFrame: Labor productivity data
    """
    query = """
    SELECT DATE(work_date) as date,
           employee_id,
           SUM(hours_worked) as total_hours,
           task_type,
           COUNT(*) as task_count
    FROM labour
    WHERE work_date >= date('now', '-{} days')
    GROUP BY DATE(work_date), employee_id, task_type
    ORDER BY date DESC
    """.format(days)
    return query_to_df(query)

# Visualization Functions

def plot_yield_trend(days=90, title=None):
    """
    Create yield trend visualization.
    
    Args:
        days (int): Number of days to analyze
        title (str, optional): Custom chart title
        
    Returns:
        plotly.graph_objects.Figure: Yield trend chart
    """
    df = get_production_summary(days)
    if df.empty:
        return go.Figure().add_annotation(text="No data available", 
                                        xref="paper", yref="paper",
                                        x=0.5, y=0.5, showarrow=False)
    
    df['date'] = pd.to_datetime(df['date'])
    
    fig = px.line(df, x='date', y='daily_yield',
                  title=title or f'Daily Yield Trend - Last {days} Days',
                  labels={'daily_yield': 'Daily Yield (lbs)', 'date': 'Date'})
    
    # Add moving average
    if len(df) > 7:
        df['ma_7'] = df['daily_yield'].rolling(window=7).mean()
        fig.add_scatter(x=df['date'], y=df['ma_7'], 
                       mode='lines', name='7-day Moving Average',
                       line=dict(dash='dash'))
    
    fig.update_layout(
        xaxis_title="Date",
        yaxis_title="Daily Yield (lbs)",
        showlegend=True
    )
    
    return fig

def plot_environmental_correlation(days=30):
    """
    Create environmental correlation heatmap.
    
    Args:
        days (int): Number of days to analyze
        
    Returns:
        plotly.graph_objects.Figure: Correlation heatmap
    """
    df = get_harvest_with_environment(days)
    if df.empty or len(df) < 10:
        return go.Figure().add_annotation(text="Insufficient data for correlation analysis", 
                                        xref="paper", yref="paper",
                                        x=0.5, y=0.5, showarrow=False)
    
    # Select numeric columns for correlation
    numeric_cols = ['trimmed_wt', 'avg_temp', 'avg_humidity', 'cycle_days']
    corr_df = df[numeric_cols].corr()
    
    fig = px.imshow(corr_df, 
                    title='Environmental Factors vs Yield Correlation',
                    color_continuous_scale='RdBu',
                    aspect='auto')
    
    return fig

def plot_production_efficiency():
    """
    Create production efficiency scatter plot.
    
    Returns:
        plotly.graph_objects.Figure: Production efficiency chart
    """
    df = get_harvest_with_environment(90)
    if df.empty:
        return go.Figure().add_annotation(text="No data available", 
                                        xref="paper", yref="paper",
                                        x=0.5, y=0.5, showarrow=False)
    
    fig = px.scatter(df, x='cycle_days', y='trimmed_wt',
                     color='room_name',
                     title='Harvest Yield vs Production Cycle Length',
                     labels={'cycle_days': 'Days from Spawn to Harvest',
                            'trimmed_wt': 'Trimmed Weight (lbs)'})
    
    # Add trend line
    if len(df) > 5:
        fig.add_scatter(x=df['cycle_days'], y=np.poly1d(np.polyfit(df['cycle_days'], df['trimmed_wt'], 1))(df['cycle_days']),
                       mode='lines', name='Trend Line', line=dict(dash='dash'))
    
    return fig

def plot_financial_performance(months=12):
    """
    Create financial performance chart.
    
    Args:
        months (int): Number of months to analyze
        
    Returns:
        plotly.graph_objects.Figure: Financial performance chart
    """
    df = get_financial_summary(months)
    if df.empty:
        return go.Figure().add_annotation(text="No financial data available", 
                                        xref="paper", yref="paper",
                                        x=0.5, y=0.5, showarrow=False)
    
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    
    # Revenue bars
    fig.add_trace(
        go.Bar(x=df['month'], y=df['revenue'], name="Revenue ($)"),
        secondary_y=False,
    )
    
    # Transaction count line
    fig.add_trace(
        go.Scatter(x=df['month'], y=df['transactions'], name="Transactions", mode='lines+markers'),
        secondary_y=True,
    )
    
    fig.update_xaxes(title_text="Month")
    fig.update_yaxes(title_text="Revenue ($)", secondary_y=False)
    fig.update_yaxes(title_text="Number of Transactions", secondary_y=True)
    fig.update_layout(title_text="Financial Performance Over Time")
    
    return fig

def create_dashboard_summary():
    """
    Create a comprehensive dashboard summary.
    
    Returns:
        dict: Summary statistics and charts
    """
    try:
        # Get recent data
        production_df = get_production_summary(30)
        financial_df = get_financial_summary(6)
        env_df = get_environmental_data(7)
        
        summary = {
            "total_yield_30d": production_df['daily_yield'].sum() if not production_df.empty else 0,
            "avg_daily_yield": production_df['daily_yield'].mean() if not production_df.empty else 0,
            "total_revenue_6m": financial_df['revenue'].sum() if not financial_df.empty else 0,
            "avg_temperature": env_df['temperature'].mean() if not env_df.empty else 0,
            "avg_humidity": env_df['humidity'].mean() if not env_df.empty else 0,
            "charts": {
                "yield_trend": plot_yield_trend(30),
                "financial_performance": plot_financial_performance(6),
                "environmental_correlation": plot_environmental_correlation(30)
            }
        }
        
        return summary
    
    except Exception as e:
        print(f"Error creating dashboard summary: {e}")
        return {"error": str(e)}

# Utility Functions

def export_data(query, filename, format='csv'):
    """
    Export query results to file.
    
    Args:
        query (str): SQL query
        filename (str): Output filename
        format (str): Output format ('csv', 'excel', 'json')
    """
    df = query_to_df(query)
    
    if format == 'csv':
        df.to_csv(filename, index=False)
    elif format == 'excel':
        df.to_excel(filename, index=False)
    elif format == 'json':
        df.to_json(filename, orient='records')
    
    print(f"Data exported to {filename}")

def quick_stats():
    """
    Display quick statistics about the database.
    """
    try:
        tables = list_tables()
        print(f"📊 Database Overview")
        print(f"Total tables: {len(tables)}")
        print(f"Tables: {', '.join(tables[:5])}{'...' if len(tables) > 5 else ''}")
        
        # Get record counts for main tables
        main_tables = ['harvest', 'readings_spore', 'sales_transaction', 'labour']
        for table in main_tables:
            if table in tables:
                count_df = query_to_df(f"SELECT COUNT(*) as count FROM {table}")
                if not count_df.empty:
                    print(f"{table}: {count_df['count'].iloc[0]:,} records")
    
    except Exception as e:
        print(f"Error getting stats: {e}")

# Auto-run when imported
if __name__ != "__main__":
    print("🍄 Mycelium Analytics Module Loaded!")
    print("📚 Available functions: get_production_summary(), plot_yield_trend(), create_dashboard_summary()")
    print("💡 Run quick_stats() to see database overview")
    print("🔗 Database connection ready!")
