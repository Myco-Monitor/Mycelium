# Business Page Design Document

## Overview
The Business page serves as the central hub for managing all business operations and financial aspects of the mushroom farm. It provides comprehensive management tools for farms, employees, inventory, production tracking, sales management, and financial reporting with real-time calculations and business intelligence.

---

## Database Tables Involved

### Core Business Tables:
- **farms**: Farm locations and management
- **grow_rooms**: Production facility management
- **employees**: Staff management and roles
- **customers**: Customer relationship management

### Inventory Management Tables:
- **product_categories**: Product type definitions
- **cost_of_goods**: Inventory purchases and tracking
- **loss_of_goods**: Waste and loss tracking

### Production Tables:
- **spawn**: Spawn batch production tracking
- **bulk**: Bulk substrate production
- **harvest**: Harvest yield tracking
- **labour**: Staff time and task tracking
- **utilities**: Operational expense tracking

### Sales and Revenue Tables:
- **sales_transaction**: Sales order management
- **sales_detail**: Line-item sales tracking with harvest linkage

---

## Page Structure and Sections

### Section 1: Business Overview Dashboard

**Purpose**: Real-time business health snapshot with key performance indicators

**Display Elements**:
- **Inventory On Hand Summary**:
  - **LC (Liquid Culture) On Hand**: Count from cost_of_goods where category_type = 'liquid_culture' minus item_used
  - **Spawn On Hand**: Count from cost_of_goods where category_type = 'spawn' minus item_used
  - **Substrate On Hand**: Count from cost_of_goods where category_type = 'substrate' minus item_used
  - **Staff Hours (Current Period)**: Sum of hours_worked from labour table for current month

**Calculation Logic**:
```sql
-- Inventory calculations
SELECT 
    pc.category_type,
    SUM(cog.item_count - cog.item_used) as on_hand_count,
    SUM((cog.weight_lbs * cog.item_count) - cog.used_weight) as on_hand_weight
FROM cost_of_goods cog
JOIN product_categories pc ON cog.item_id = pc.item_id
WHERE pc.active = 1
GROUP BY pc.category_type;

-- Staff hours for current month
SELECT SUM(hours_worked) as total_hours
FROM labour 
WHERE strftime('%Y-%m', work_date) = strftime('%Y-%m', 'now');
```

**Visual Design**:
- Card-based layout with color-coded indicators
- Progress bars showing inventory levels vs. targets
- Trend arrows showing month-over-month changes

---

### Section 2: Navigation Buttons

**Layout**: Grid of large, clearly labeled navigation buttons leading to specialized management sections

#### 2.1 Farms Management
**Button Label**: "Farms & Grow Rooms"
**Target Tables**: farms, grow_rooms
**Functionality**:
- Farm location management and status tracking
- Grow room configuration and capacity planning
- Active/inactive status management with deactivation reasons
- Farm-level reporting and analytics

#### 2.2 Employee Management
**Button Label**: "Employees"
**Target Tables**: employees
**Functionality**:
- Employee roster management with roles and contact information
- Pay rate configuration and employment history
- Active/inactive status tracking
- Employee performance metrics integration

#### 2.3 Inventory Management
**Button Label**: "Inventory"
**Target Tables**: product_categories, cost_of_goods, loss_of_goods
**Functionality**:
- Product category definition and management
- Purchase order tracking and cost management
- Inventory usage monitoring with automated depletion calculations
- Loss tracking with categorized reasons (contamination, spoilage, etc.)
- Reorder point alerts and supplier management

#### 2.4 Production Management
**Button Label**: "Production"
**Target Tables**: spawn, bulk, harvest, labour, utilities
**Functionality**:
- **Spawn Production**: Batch tracking from inoculation to completion
- **Bulk Substrate**: Colonization monitoring and batch management
- **Harvest Tracking**: Yield recording with quality metrics
- **Labour Management**: Task-based time tracking and productivity analysis
- **Utilities Tracking**: Operational expense monitoring with due date alerts

#### 2.5 Sales Management
**Button Label**: "Sales"
**Target Tables**: sales_transaction, sales_detail, customers
**Functionality**:
- Customer relationship management with contact tracking
- Sales order processing with harvest traceability
- Price management and customer-specific pricing
- Sales performance analytics and customer segmentation

#### 2.6 Financial Dashboard
**Button Label**: "Financials"
**Target Tables**: All revenue and expense tables
**Functionality**:
- **Total Revenue**: Sum from sales_transaction.total_amount where active = 1
- **Total Expenses**: Combined sum from utilities.util_cost + labour costs + cost_of_goods.item_cost + loss_of_goods value
- **Net Profit/Loss**: Revenue minus Total Expenses
- **Gross Profit Margin (%)**: ((Revenue - Cost of Goods Sold) / Revenue) * 100
- **Net Profit Margin (%)**: (Net Profit / Revenue) * 100

**Financial Calculations**:
```sql
-- Total Revenue
SELECT SUM(total_amount) as total_revenue
FROM sales_transaction 
WHERE active = 1;

-- Total Expenses
SELECT 
    (SELECT SUM(util_cost) FROM utilities) +
    (SELECT SUM(e.emp_rate * l.hours_worked) 
     FROM labour l JOIN employees e ON l.emp_id = e.emp_id) +
    (SELECT SUM(item_cost) FROM cost_of_goods) +
    (SELECT SUM(quantity * estimated_value) FROM loss_of_goods)
    as total_expenses;

-- Gross Profit Margin calculation
SELECT 
    ((revenue - cogs) / revenue) * 100 as gross_margin
FROM (
    SELECT 
        (SELECT SUM(total_amount) FROM sales_transaction WHERE active = 1) as revenue,
        (SELECT SUM(item_cost) FROM cost_of_goods) as cogs
);
```

---

### Section 3: Quick Actions Panel

**Purpose**: Frequently used business operations accessible from main dashboard

**Quick Action Buttons**:
- **Add New Sale**: Direct link to sales entry form
- **Record Harvest**: Quick harvest logging with weight and quality
- **Log Labour Hours**: Employee time tracking entry
- **Add Inventory**: Purchase order entry for new stock
- **Pay Utility Bill**: Utility expense recording
- **Generate Report**: Export business data in various formats

**Recent Activity Feed**:
- Last 10 sales transactions with customer and amount
- Recent harvest entries with yield data
- Pending utility bills approaching due dates
- Low inventory alerts requiring attention

---

### Section 4: Business Intelligence Widgets

**Performance Metrics**:
- **Production Efficiency**: Harvest yield per batch over time
- **Labour Productivity**: Revenue per labour hour
- **Inventory Turnover**: Days of inventory on hand
- **Customer Analysis**: Top customers by revenue and frequency

**Trend Charts**:
- Monthly revenue and expense trends
- Seasonal production patterns
- Employee productivity metrics
- Inventory usage patterns

**Alert System**:
- Low inventory warnings with reorder suggestions
- Overdue utility bills requiring immediate attention
- Production batches ready for next stage
- Employees approaching overtime thresholds

---

## User Experience Features

### Responsive Design
- Mobile-optimized layouts for field data entry
- Touch-friendly buttons for production floor use
- Offline capability for remote farm locations

### Role-Based Access
- **Admin**: Full access to all business functions and financial data
- **Manager**: Production and sales management, limited financial access
- **Employee**: Time tracking and basic production data entry
- **Viewer**: Read-only access to reports and dashboards

### Data Export and Reporting
- **Financial Reports**: P&L statements, expense breakdowns, tax reporting
- **Production Reports**: Yield analysis, batch tracking, efficiency metrics
- **Inventory Reports**: Stock levels, usage patterns, reorder analysis
- **Labour Reports**: Payroll data, productivity analysis, task tracking

### Integration Points
- **Accounting Software**: Export financial data for tax preparation
- **Inventory Management**: Barcode scanning for stock management
- **Customer Portal**: Order tracking and invoice access
- **Mobile Apps**: Field data collection and real-time updates

---

## Technical Implementation Notes

### Database Optimization
- Indexed queries for financial calculations
- Cached dashboard metrics updated hourly
- Archived historical data for performance
- Backup procedures for business-critical data

### Security Considerations
- Encrypted financial data storage
- Audit trails for all business transactions
- Role-based access controls
- Regular security updates and monitoring

### Performance Requirements
- Dashboard loads within 2 seconds
- Real-time inventory updates
- Concurrent user support (up to 10 users)
- 99.9% uptime for business operations

---

## Future Enhancements

### Advanced Analytics
- Predictive inventory management
- Seasonal demand forecasting
- Automated pricing optimization
- Customer lifetime value analysis

### Automation Features
- Automated reorder points and purchase orders
- Scheduled financial report generation
- Alert notifications via email/SMS
- Integration with farm automation systems

### Business Intelligence
- Executive dashboard with KPI tracking
- Comparative analysis across multiple farms
- Market trend integration
- Profitability analysis by product line
