# Analytics Page Design Document

## Overview
The Analytics page provides advanced data analysis capabilities through an integrated Jupyter notebook environment. Users can perform custom queries, create sophisticated visualizations, and conduct deep-dive analysis of their mushroom farm operations using the full power of Python data science tools.

---

## Technical Architecture

### Integration Approach: Embedded JupyterLab
**Primary Method**: JupyterLab server running alongside the main Dash application

**Components**:
- **JupyterLab Server**: Separate process serving notebooks on dedicated port
- **Database Connection**: Pre-configured SQLite connection to Mycelium database
- **Pre-loaded Libraries**: pandas, plotly, matplotlib, seaborn, numpy, scipy
- **Custom Modules**: Mycelium-specific helper functions and data connectors

**Alternative Approaches**:
1. **Voilà Integration**: Convert notebooks to interactive web apps
2. **Panel/Param**: Create dashboard-style interfaces from notebook code
3. **Custom Notebook Interface**: Build simplified notebook cells within Dash

---

## Database Tables Available for Analysis

### Core Data Sources:
- **Environmental Data**: `readings_spore`, `readings_hyphae`, `readings_weather`
- **Production Data**: `spawn`, `bulk`, `harvest`
- **Business Data**: `sales_transaction`, `sales_detail`, `cost_of_goods`, `labour`
- **Operational Data**: `employees`, `customers`, `utilities`, `loss_of_goods`

### Pre-configured Database Connections:
```python
import sqlite3
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta

# Pre-configured database connection
DB_PATH = '/path/to/mycelium.db'

def get_connection():
    """Get database connection with row factory for easier data access"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def query_to_df(query, params=None):
    """Execute query and return pandas DataFrame"""
    with get_connection() as conn:
        return pd.read_sql_query(query, conn, params=params or {})
```

---

## Page Structure and Sections

### Section 1: Analytics Dashboard

**Purpose**: Quick access to common analytics tasks and notebook management

**Dashboard Elements**:
- **Notebook Library**: Pre-built analysis templates
- **Recent Notebooks**: Last accessed user notebooks
- **Quick Queries**: Common data extractions with one-click execution
- **Data Export**: Download datasets in various formats (CSV, JSON, Excel)

**Pre-built Notebook Templates**:
- **Production Analysis**: Yield trends, batch efficiency, seasonal patterns
- **Financial Analysis**: Revenue trends, cost analysis, profitability by product
- **Environmental Monitoring**: Temperature/humidity correlations, device performance
- **Labour Analytics**: Productivity analysis, task efficiency, payroll insights
- **Customer Analysis**: Sales patterns, customer segmentation, retention analysis

### Section 2: Interactive Jupyter Environment

**Notebook Interface Features**:
- **Full JupyterLab Environment**: Complete IDE with file browser, terminal access
- **Pre-loaded Data Connectors**: Helper functions for common database queries
- **Visualization Templates**: Plotly chart templates for farm-specific metrics
- **Export Capabilities**: Save charts as images, export data, share notebooks

**Example Notebook Structure**:
```python
# Cell 1: Data Loading
from mycelium_analytics import *

# Load recent harvest data
harvest_df = query_to_df("""
    SELECT h.harvest_ts, h.total_wt, h.trimmed_wt, 
           b.start_ts as bulk_start, s.start_ts as spawn_start,
           gr.room_name, f.farm_name
    FROM harvest h
    JOIN bulk b ON h.bulk_id = b.bulk_id
    JOIN spawn s ON b.spawn_id = s.spawn_id
    JOIN grow_rooms gr ON h.room_id = gr.room_id
    JOIN farms f ON gr.farm_id = f.farm_id
    WHERE h.harvest_ts >= date('now', '-90 days')
    ORDER BY h.harvest_ts DESC
""")

# Cell 2: Data Processing
harvest_df['harvest_date'] = pd.to_datetime(harvest_df['harvest_ts'])
harvest_df['cycle_days'] = (
    harvest_df['harvest_date'] - pd.to_datetime(harvest_df['spawn_start'])
).dt.days

# Cell 3: Visualization
fig = px.scatter(harvest_df, 
                x='cycle_days', 
                y='trimmed_wt',
                color='room_name',
                title='Harvest Yield vs Production Cycle Length',
                labels={'cycle_days': 'Days from Spawn to Harvest',
                       'trimmed_wt': 'Trimmed Weight (lbs)'})
fig.show()
```

### Section 3: Advanced Analytics Tools

**Statistical Analysis Capabilities**:
- **Correlation Analysis**: Identify relationships between environmental factors and yield
- **Trend Analysis**: Time series analysis with seasonal decomposition
- **Predictive Modeling**: Simple forecasting models for production planning
- **A/B Testing**: Compare different growing techniques or conditions

**Machine Learning Integration**:
```python
# Example: Yield prediction model
from sklearn.ensemble import RandomForestRegressor
from sklearn.model_selection import train_test_split

# Feature engineering for yield prediction
features = ['temp_avg', 'humidity_avg', 'co2_avg', 'cycle_days', 'room_id']
X = environmental_harvest_df[features]
y = environmental_harvest_df['trimmed_wt']

# Train simple prediction model
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2)
model = RandomForestRegressor(n_estimators=100)
model.fit(X_train, y_train)

# Feature importance analysis
importance_df = pd.DataFrame({
    'feature': features,
    'importance': model.feature_importances_
}).sort_values('importance', ascending=False)

px.bar(importance_df, x='importance', y='feature', 
       title='Factors Most Important for Yield Prediction')
```

### Section 4: Collaborative Analytics

**Sharing and Collaboration**:
- **Notebook Sharing**: Export notebooks for team collaboration
- **Report Generation**: Convert analysis to PDF/HTML reports
- **Scheduled Analysis**: Automated notebook execution for regular reports
- **Version Control**: Track changes to analysis notebooks

**Template Library**:
- **Quality Control**: Contamination rate analysis, batch failure investigation
- **Efficiency Metrics**: Labor productivity, resource utilization
- **Market Analysis**: Price trends, customer demand patterns
- **Operational Optimization**: Equipment utilization, energy efficiency

---

## Implementation Roadmap

### Phase 1: Basic Integration (Immediate)
- Set up JupyterLab server alongside Dash app
- Create database connection helpers
- Build basic notebook templates
- Implement simple embedding in web interface

### Phase 2: Enhanced Features (Short-term)
- Custom Mycelium analytics library
- Pre-built visualization templates
- Data export and sharing capabilities
- User authentication and notebook security

### Phase 3: Advanced Analytics (Medium-term)
- Machine learning model templates
- Automated report generation
- Real-time data streaming to notebooks
- Advanced statistical analysis tools

### Phase 4: Enterprise Features (Long-term)
- Multi-farm comparative analysis
- Industry benchmarking data integration
- Advanced predictive modeling
- Custom dashboard creation from notebooks

---

## Technical Requirements

### Server Configuration:
```yaml
# docker-compose.yml addition
jupyterlab:
  image: jupyter/scipy-notebook:latest
  ports:
    - "8888:8888"
  volumes:
    - ./notebooks:/home/jovyan/work
    - ./data:/home/jovyan/data
    - ./mycelium.db:/home/jovyan/mycelium.db
  environment:
    - JUPYTER_ENABLE_LAB=yes
    - JUPYTER_TOKEN=your-secure-token
  command: start-notebook.sh --NotebookApp.token='your-secure-token'
```

### Required Python Packages:
```txt
# requirements-analytics.txt
jupyter
jupyterlab
pandas>=1.3.0
plotly>=5.0.0
matplotlib>=3.5.0
seaborn>=0.11.0
numpy>=1.21.0
scipy>=1.7.0
scikit-learn>=1.0.0
sqlite3
sqlalchemy
```

### Custom Analytics Module:
```python
# mycelium_analytics.py
"""Custom analytics module for Mycelium farm data analysis"""

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import sqlite3

class MyceliumAnalytics:
    def __init__(self, db_path):
        self.db_path = db_path
    
    def get_production_summary(self, days=30):
        """Get production summary for specified period"""
        query = """
        SELECT DATE(harvest_ts) as date, 
               SUM(trimmed_wt) as daily_yield,
               COUNT(*) as harvest_count
        FROM harvest 
        WHERE harvest_ts >= date('now', '-{} days')
        GROUP BY DATE(harvest_ts)
        ORDER BY date
        """.format(days)
        return self.query_to_df(query)
    
    def plot_yield_trend(self, days=90):
        """Create yield trend visualization"""
        df = self.get_production_summary(days)
        fig = px.line(df, x='date', y='daily_yield',
                     title=f'Daily Yield Trend - Last {days} Days')
        return fig
    
    def environmental_correlation(self, metric='trimmed_wt'):
        """Analyze correlation between environmental factors and yield"""
        # Complex query joining environmental and harvest data
        # Implementation would include sophisticated data joining
        pass
```

---

## Security and Access Control

### User Permissions:
- **Admin**: Full notebook access, can install packages, access all data
- **Analyst**: Read/write notebooks, limited package installation
- **Viewer**: Read-only access to shared notebooks and reports
- **Basic User**: Access to pre-built templates only

### Data Security:
- Notebook sandboxing to prevent unauthorized data access
- Audit logging of all database queries
- Secure token-based authentication
- Regular backup of analysis notebooks

### Resource Management:
- CPU and memory limits per user session
- Automatic cleanup of idle notebooks
- Disk space monitoring and cleanup
- Concurrent user session limits

---

## User Experience Features

### Guided Analytics:
- **Tutorial Notebooks**: Step-by-step guides for common analysis tasks
- **Interactive Widgets**: ipywidgets for parameter adjustment
- **Data Validation**: Automatic checks for data quality and completeness
- **Error Handling**: User-friendly error messages and debugging tips

### Integration with Main App:
- **Seamless Navigation**: Direct links from main dashboard to relevant notebooks
- **Data Synchronization**: Real-time updates when new data is collected
- **Export to Dashboard**: Convert notebook visualizations to dashboard widgets
- **Alert Integration**: Notebook-based alerts and monitoring

---

## Future Enhancements

### Advanced Features:
- **Real-time Streaming**: Live data feeds for continuous monitoring
- **Collaborative Editing**: Multiple users working on same notebook
- **Version Control**: Git integration for notebook versioning
- **API Integration**: Connect to external data sources and services

### AI/ML Capabilities:
- **Automated Insights**: AI-powered pattern detection and recommendations
- **Natural Language Queries**: Convert plain English to SQL queries
- **Predictive Maintenance**: Equipment failure prediction models
- **Optimization Algorithms**: Automated parameter tuning for growing conditions

This analytics page design provides a powerful, flexible foundation that can grow with your needs while maintaining the professional structure of your other documentation.
