# Devices Page Design Document

## Overview
The Devices page serves as the central hub for managing and monitoring all IoT devices in the mushroom farm ecosystem. It provides comprehensive device status monitoring, configuration management, and control capabilities for both Spore (environmental sensors) and Hyphae (control units) devices.

The page focuses on three core functionalities:
1. **Device Addition & Management**: Adding devices via IP address with automatic data population
2. **Device Configuration**: Managing device settings with PIN verification
3. **Device Status Monitoring**: Visualizing device status with refresh capabilities

---

## Database Tables Involved

### Primary Device Tables:
- **device_spore**: Environmental monitoring devices
- **device_hyphae**: Control and relay management devices
- **grow_rooms**: Location context for devices

### Configuration Tables:
- **relay_settings**: Relay naming and grouping
- **schedule_settings**: Time-based automation
- **dynamic_settings**: Threshold-based automation

### Data Tables (for context):
- **readings_spore**: Recent sensor data
- **readings_hyphae**: Recent relay states

---

## Page Structure and Sections

### Section 1: Device Overview Dashboard

**Purpose**: Quick status overview of all devices with automated discovery and refresh capabilities

**Display Elements**:
- Total device count (Spore + Hyphae)
- Online/Offline status summary with color indicators (green for online, red for offline)
- Recent alerts or issues with timestamp
- Network health indicators with signal strength visualization
- Refresh button to update all device statuses simultaneously

**Device Addition Interface**:
- **Add Spore Device Button**: Opens a modal with:
  - IP address input field with validation
  - Optional room assignment dropdown
  - "Add Device" confirmation button
  - Status indicator during connection process
  - Error handling with clear messages
  
- **Add Hyphae Device Button**: Opens a modal with:
  - IP address input field with validation
  - Optional PIN input for secure operations
  - Optional room assignment dropdown
  - "Add Device" confirmation button
  - Status indicator during connection process
  - Error handling with clear messages

**Automated Device Addition Process**:
- **For Spore Devices**: When user submits IP address, system:
  - Validates IP format and accessibility
  - Calls `/spore-config` endpoint to retrieve configuration
  - Extracts device_name, measurement_interval, temperature_offset, etc.
  - Discovers MAC address via network utilities
  - Auto-populates database with progressive feedback
  - Confirms successful addition with device details summary
  
- **For Hyphae Devices**: When user submits IP address, system:
  - Validates IP format and accessibility
  - Calls `/hyphae-config` endpoint to retrieve configuration
  - Calls additional endpoints for system info and relay configuration
  - Discovers MAC address via network utilities
  - Auto-populates database with progressive feedback
  - Sets up default relay configurations
  - Confirms successful addition with device details summary

**Device Refresh Options**:
- **Refresh All** button to update all device statuses
- **Selective Refresh** option with device checkboxes
- **Auto-Refresh** toggle with interval selection (30s, 1m, 5m)
- Visual indicators showing refresh in progress

**Network Discovery Features**:
- **Scan Network Button**: Automated discovery using existing DiscoveryService
- **Bulk Device Registration**: Register multiple discovered devices at once
- **MAC Address Resolution**: Use system tools (ping, ARP table lookup) to get MAC addresses
- **Device Validation**: Verify device endpoints are accessible before registration

### Section 2: Device Selection and Management Interface

**Device Selection UI**:
- **Device Type Tabs**: Toggle between Spore and Hyphae device views
- **Device Dropdown**: Select specific devices to view/edit
  - Organized by room and device type
  - Search functionality by name or IP
  - Status indicators (online/offline) in dropdown
- **Multi-select Option**: For bulk operations on multiple devices
- **Filter Controls**: Filter by status, room, or last activity

**Device Display Options**:
- **Card View**: Visual representation with status indicators
- **Table View**: Detailed information in tabular format
- **Map View**: Spatial representation of device locations

### Section 3: Spore Devices Management

**Table: device_spore**

**Display-Only Fields**:
- **device_id**: Hidden, used for operations
- **room_id**: Displayed as room name via join with grow_rooms
- **mac_address**: Network identifier (display only)
- **firmware_version**: Current firmware version
- **is_online**: Real-time status with color indicators
- **last_update**: Timestamp of last communication
- **created_at**: Device registration date
- **sensor_readings**: Latest temperature, humidity, CO2 values with trend indicators

**Editable Fields**:
- **device_name**: Text input for custom naming
- **ip_address**: Network configuration (admin only)
- **hyphae_id**: Dropdown to link with Hyphae device
- **hyphae_present**: Auto-updated based on hyphae_id
- **active**: Toggle switch for device activation
- **deactivation_reason**: Textarea (shown when active=0)

**Interactive Features**:
- **Refresh Button**: Update individual device status and readings
- **Settings Button**: Opens configuration modal with:
  - Sensor calibration options
  - Measurement interval adjustment
  - Temperature offset configuration
  - Altitude compensation settings
  - PIN verification for sensitive changes
- **View Readings Button**: Opens detailed readings history
- **Export Data Button**: Download device data as CSV/JSON

### Section 4: Hyphae Devices Management

**Table: device_hyphae**

**Display-Only Fields**:
- **device_id**: Hidden identifier
- **room_id**: Displayed as room name
- **mac_address**: Network identifier
- **firmware_version**: Current version
- **is_online**: Real-time status indicators
- **last_update**: Last communication timestamp
- **created_at/updated_at**: Audit timestamps
- **relay_status**: Visual indicators for each relay (on/off)

**Editable Fields**:
- **device_name**: Text input for naming
- **ip_address**: Network configuration (admin only)
- **mode_enabled**: Dropdown (0=Offline, 1=Testing, 2=Running)
- **mode_operation**: Dropdown (0=Schedule, 1=Dynamic)
- **active**: Toggle for device status
- **deactivation_reason**: Textarea when inactive

**Control Features**:
- **PIN Authentication**: Required for all control operations
  - PIN input field with secure entry
  - Temporary PIN caching option (for session)
  - PIN timeout settings
- **Relay Control Panel**:
  - Individual relay toggles with status indicators
  - Group controls for related relays
  - Manual override options
- **Mode Configuration**:
  - Mode switching with confirmation
  - Schedule configuration interface
  - Dynamic threshold settings
- **Device Actions**:
  - Refresh device status
  - Sync configuration
  - Test relays
  - Reset device

### Section 5: Advanced Configuration

#### 5.1 Relay Settings Management
**Table: relay_settings**

**PIN-Protected Configuration Interface**:
- PIN verification required for all configuration changes
- Clear indication of which operations require PIN
- Option to remember PIN for session duration

**Display/Edit Grid**:
- **device_id**: Context (current device)
- **relay_number**: Display (1-6)
- **relay_name**: Editable text input
- **group_num**: Dropdown (1-6) for logical grouping
- **created_at/updated_at**: Timestamps
- **current_status**: Real-time relay status indicator

**Features**:
- Bulk rename functionality with confirmation
- Group assignment wizard with visual grouping
- Import/Export relay configurations
- Test relay functionality with PIN verification
- Visual feedback during relay operations

#### 5.2 Schedule Settings Management (WRONG)
**Table: schedule_settings**

**Configuration Interface**:
- **device_id**: Context
- **group_num**: Group selector (1-6)
- **on_time**: Time picker (HH:MM format)
- **off_time**: Time picker (HH:MM format)
- **days_active**: Day selector (checkboxes for each day)
- **created_at/updated_at**: Audit trail

**Features**:
- Visual timeline view of schedules with drag-and-drop editing
- Bulk schedule application across multiple devices
- Schedule conflict detection and resolution
- Weekly/daily schedule templates
- Schedule preview showing next 24 hours of activity
- PIN verification for schedule changes

#### 5.3 Dynamic Settings Management
**Table: dynamic_settings**

**Threshold Configuration**:
- **device_id**: Context
- **group_num**: Group selector (1-3)
- **parameter**: Dropdown (temperature, humidity, co2)
- **low_threshold**: Number input with validation
- **high_threshold**: Number input with validation
- **behavior**: Toggle (0=Turn OFF when exceeded, 1=Turn ON when exceeded)
- **hysteresis**: Configurable deadband to prevent oscillation
- **created_at/updated_at**: Timestamps

**Features**:
- Real-time threshold visualization with current readings
- Historical parameter monitoring graphs
- Threshold testing simulator with PIN verification
- Alert configuration for threshold breaches
- Threshold templates for common scenarios
- PIN verification for threshold changes

---

## Automated Device Addition Workflow

### Device Addition User Interface

**Common Elements for Both Device Types**:
- **IP Address Input**: With validation and format hints
- **Room Assignment**: Dropdown with option to create new room
- **Connection Status**: Real-time feedback during connection process
- **Progress Indicator**: Shows current step in the multi-step process
- **Error Display**: Clear error messages with troubleshooting suggestions

**Spore-Specific Elements**:
- **Device Type Confirmation**: Verifies device is a Spore sensor
- **Sensor Configuration Preview**: Shows detected sensors and capabilities

**Hyphae-Specific Elements**:
- **PIN Input**: For secure operations (optional during initial setup)
- **Relay Configuration Preview**: Shows detected relays
- **Operation Mode Selection**: Schedule or Dynamic mode

### Add Spore Device Process

**User Input**: IP address (e.g., "192.168.1.100")

**Backend Process with Progressive Feedback**:
1. **Validate IP Address** (5%)
   - Check format and network accessibility
   - Show "Validating IP address..." status
   - Proceed only if reachable

2. **Device Type Verification** (15%)
   - Attempt to access Spore-specific endpoints
   - Show "Verifying device type..." status
   - Confirm device is a Spore sensor

3. **Configuration Retrieval** (30%)
   - Call `/spore-config` endpoint
   - Show "Retrieving device configuration..." status
   - Parse HTML response for configuration values
   ```python
   GET http://{ip_address}/spore-config
   # Returns configuration including device_name, measurement_interval, etc.
   ```

4. **MAC Address Discovery** (50%)
   - Show "Identifying device hardware..." status
   - Try multiple methods in sequence:
     ```python
     # Method 1: Direct ARP lookup
     mac = get_mac_from_arp(ip_address)
     
     # Method 2: Ping then ARP
     if not mac:
         mac = get_mac_with_ping(ip_address)
     
     # Method 3: Network scan
     if not mac:
         mac = get_mac_from_network_scan(ip_address)
     ```
   - Allow manual entry if automatic discovery fails

5. **Data Preparation** (70%)
   - Show "Preparing device data..." status
   - Format and validate all collected data
   - Check for duplicate devices
   - Present summary for user confirmation

6. **Database Registration** (85%)
   - Show "Registering device..." status
   - Create new device_spore record
   - Set initial status and timestamps
   ```python
   device_id = create_device_spore(
       device_name=config['device_name'],
       ip_address=ip_address,
       mac_address=mac,
       room_id=selected_room_id,
       # Additional fields from configuration
   )
   ```

7. **Finalization** (100%)
   - Show "Device added successfully!" status
   - Display device summary with link to device details
   - Offer next steps (configure settings, view readings)

### Add Hyphae Device Process

**User Input**: IP address and optional PIN

**Backend Process with Progressive Feedback**:
1. **Validate IP Address** (5%)
   - Check format and network accessibility
   - Show "Validating IP address..." status

2. **Device Type Verification** (15%)
   - Attempt to access Hyphae-specific endpoints
   - Show "Verifying device type..." status

3. **Basic Configuration Retrieval** (25%)
   - Call `/hyphae-config` endpoint
   - Show "Retrieving basic configuration..." status
   ```python
   GET http://{ip_address}/hyphae-config
   # Returns HTML form with configuration values
   ```

4. **System Information Retrieval** (40%)
   - Call `/api/system/info` endpoint
   - Show "Retrieving system information..." status
   ```python
   GET http://{ip_address}/api/system/info
   # Returns JSON with system information
   ```

5. **Relay Configuration Retrieval** (55%)
   - Call `/api/relay/config` endpoint
   - Show "Retrieving relay configuration..." status
   ```python
   GET http://{ip_address}/api/relay/config
   # Returns JSON with relay configuration
   ```
   - If PIN provided, attempt authenticated operations

6. **MAC Address Discovery** (70%)
   - Show "Identifying device hardware..." status
   - Use same methods as Spore devices
   - Allow manual entry if automatic discovery fails

7. **Data Preparation** (80%)
   - Show "Preparing device data..." status
   - Format and validate all collected data
   - Map configuration values to database fields
   - Present summary for user confirmation

8. **Database Registration** (90%)
   - Show "Registering device..." status
   - Create device_hyphae record
   - Create relay_settings entries for each relay
   - Set initial mode and status

9. **Finalization** (100%)
   - Show "Device added successfully!" status
   - Display device summary with link to device details
   - Offer next steps (configure relays, set schedules)

### Error Handling and Recovery

**Comprehensive Error Handling**:
- **Connection Timeout**: 
  - Clear message: "Unable to connect to device at {ip_address}"
  - Suggestions: "Check that the device is powered on and connected to the network"
  - Retry option with increased timeout

- **Invalid Device Type**: 
  - Clear message: "The device at {ip_address} does not appear to be a {expected_type} device"
  - Option to try alternative device type
  - Manual override option with warning

- **Duplicate Device Detection**:
  - Clear message: "A device with this {identifier} already exists"
  - Options: "Update existing device", "Register as new device", or "Cancel"
  - Side-by-side comparison of existing vs. new configuration

- **Partial Configuration Retrieval**:
  - Warning: "Some device information could not be retrieved"
  - Option to continue with partial information
  - Manual entry fields for missing data

- **PIN Authentication Failure**:
  - Clear message: "PIN authentication failed"
  - Option to retry with different PIN
  - Proceed with limited functionality (read-only)

**Success Confirmation**:
- Visual confirmation with device details
- Quick-action buttons for common next steps
- Option to add another device of same type

---

## Technical Design

### Frontend Implementation

#### Component Architecture
- **Device Dashboard Component**: Central container managing all device-related views
  - Implements device selection, filtering, and view switching
  - Manages state for selected devices and refresh operations

- **Device Addition Modal**: Multi-step wizard for adding devices
  - Progress tracking with step indicators
  - Validation at each step with clear feedback
  - Asynchronous API calls with loading states

- **Device Configuration Components**: Device-specific configuration interfaces
  - PIN authentication handling with secure input
  - Form validation with immediate feedback
  - Real-time preview of configuration changes

#### State Management
- **Device Selection State**: Tracks currently selected device(s)
  - Single device selection for detailed view/configuration
  - Multi-device selection for bulk operations

- **Refresh State**: Manages refresh operations
  - Tracks last refresh time per device
  - Handles auto-refresh intervals
  - Provides visual feedback during refresh

- **Error Handling State**: Centralized error management
  - Categorizes errors by severity and type
  - Provides appropriate user feedback
  - Offers recovery options when possible

### Backend Implementation

#### API Endpoints

**Device Discovery and Management**:
```python
# Device discovery endpoint
GET /api/devices/discover?network={network_cidr}

# Device addition endpoints
POST /api/devices/spore/add
POST /api/devices/hyphae/add

# Device refresh endpoints
POST /api/devices/refresh/{device_id}
POST /api/devices/refresh/all
```

**Device Configuration**:
```python
# Get device configuration
GET /api/devices/{device_type}/{device_id}/config

# Update device configuration (requires PIN for Hyphae)
PUT /api/devices/{device_type}/{device_id}/config

# Relay control endpoints (requires PIN)
POST /api/devices/hyphae/{device_id}/relay/{relay_number}/toggle
POST /api/devices/hyphae/{device_id}/relay/group/{group_number}/toggle
```

#### Security Implementation
- **PIN Authentication**: 
  - Secure PIN handling with rate limiting
  - Temporary PIN caching with configurable timeout
  - PIN verification for all sensitive operations

- **API Security**:
  - Input validation on all endpoints
  - CSRF protection for form submissions
  - Rate limiting to prevent brute force attacks

### Database Optimization

- **Efficient Queries**: Optimized queries for device listing and filtering
  ```python
  # Example optimized query for device listing with room info
  SELECT d.*, r.room_name 
  FROM device_spore d 
  LEFT JOIN grow_rooms r ON d.room_id = r.room_id
  WHERE d.active = 1
  ORDER BY d.is_online DESC, d.device_name
  ```

- **Transaction Management**: 
  - Atomic operations for device addition and configuration
  - Rollback capability for failed operations

- **Caching Strategy**:
  - Cache device configurations with TTL
  - Cache device status with short TTL
  - Invalidate cache on configuration changes

---

## User Experience Design

### Responsive Interface
- **Desktop Layout**: Full-featured interface with side-by-side panels
  - Device list panel (left) + Device details panel (right)
  - Multi-column data tables with sorting and filtering
  - Expanded visualization options

- **Tablet Layout**: Optimized for medium screens
  - Collapsible panels with smooth transitions
  - Touch-friendly controls with appropriate sizing
  - Simplified visualizations that maintain clarity

- **Mobile Layout**: Essential functionality for small screens
  - Single-panel view with navigation between sections
  - Simplified controls focused on most common actions
  - Vertical stacking of information with progressive disclosure

### Real-Time Feedback

- **Device Status Indicators**:
  - Color-coded status (green=online, yellow=warning, red=offline)
  - Animated indicators during refresh operations
  - Status change notifications

- **Operation Feedback**:
  - Clear success/failure messages for all operations
  - Progress indicators for multi-step processes
  - Estimated time remaining for longer operations

- **Data Freshness Indicators**:
  - Last updated timestamp for each device
  - Visual indication of stale data
  - Auto-refresh countdown when enabled

### Accessibility Features

- **Keyboard Navigation**: Full keyboard support with logical tab order

- **Screen Reader Support**: 
  - ARIA labels and roles for all interactive elements
  - Status announcements for dynamic content changes
  - Alternative text for all visual indicators

- **Visual Accessibility**:
  - High contrast mode option
  - Adjustable text size
  - Multiple visual themes (light/dark/high contrast)

---

## Implementation Considerations

### Performance Optimization
- **Lazy Loading**: Load device details only when selected
- **Pagination**: Implement pagination for large device lists
- **Throttled API Calls**: Limit refresh frequency to prevent overloading

### Error Resilience
- **Offline Support**: Graceful degradation when network is unavailable
- **Retry Mechanisms**: Automatic retry for transient failures
- **Fallback Options**: Alternative methods when primary approach fails

### Future Extensibility
- **Plugin Architecture**: Allow for new device types to be added
- **Configuration Templates**: Support for saving and applying configuration templates
- **Bulk Operations API**: Framework for performing operations across multiple devices

---

This comprehensive design enables effective monitoring and control of devices while providing an excellent user experience. The implementation balances performance, security, and usability to create a robust and flexible device management system.

