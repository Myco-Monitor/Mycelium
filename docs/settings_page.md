# Settings Page Design Document

## Overview
The Settings page in the Mycelium project is designed to allow users to manage their profiles, farm settings, and grow room configurations. It integrates user-specific preferences with farm-level management while respecting role-based access controls.

---

## Sections and Layout

### Section 1: User Profile Settings

- **Display-Only Fields:**
  - **user_id:** Used internally for user identification. Hidden from the UI.
  - **user_name:** Display only. Changes require admin approval.
  - **user_role:** Display-only for security reasons.
  - **created_at / updated_at:** Shown as timestamps to track changes.

- **Editable Fields:**
  - **owm_api_key:** Input field with password masking.
  - **owm_zip_code:** Text input with validation for correct ZIP code format.
  - **timezone_name:** Dropdown allowing selection among standard US timezones.
  - **time_format:** Radio buttons to choose between 12-hour and 24-hour formats.
  - **temp_pref:** Radio buttons for Celsius or Fahrenheit preferences.
  - **reset_pin:** Password input with a confirmation field for reliability.

- **UX Features:**
  - Auto-save functionality ensuring immediate update.
  - Clear error messages on validation failures.

### Section 2: Farm Management

- **Display:**
  - Use dropdown/selectors to display farm options and associate users.
  - **farm_id, farm_name, farm_loc** displayed for context.

- **Editable Fields:**
  - **farm_name / farm_loc / farm_desc:** Text inputs with concise placeholders.
  - **active:** Checkbox to toggle the farm's active status.
  - **deactivation_reason:** Textarea available when a farm is deactivated.

- **Permissions:**
  - Changes to farms are restricted to users with farm admin rights.

### Section 3: Grow Room Management

- **Layout:**
  - Expandable lists display rooms by farm.
  - Inline edit controls for rapid updates.

- **Editable Fields:**
  - **room_name / room_desc:** Fields for room-specific identification and details.
  - **active / deactivation_reason:** Controlled in the admin panel.

- **Admin Controls:**
  - Add New Room, Edit, and Delete options with confirmation.

---

## Technical Design

### Frontend
- **Framework:** Recommend using React or Vue for state management and lifecycle handling.
- **Responsive Design:** Ensure the page is usable on both desktop and mobile.
- **Theme Integration:** Utilize existing theme components, ensuring consistency.

### Backend
- **API Calls:**
  - Granular endpoints for updating user, farm, and room details.
  - Handle validation errors with informative responses.

- **Security:**
  - Input sanitization and validation on the server-side.
  - Use JWT for authenticated API interactions.

### Database
- **Transactions:** Ensure atomic operations to maintain data consistency.
- **Role Validation:** Implement role checks before write operations.

---

## User Experience
- **Accessibility:**
  - Properly label form inputs for screen readers.
  - Maintain keyboard accessibility for all interactive elements.

- **Feedback and Confirmation:**
  - Use non-intrusive notifications for updates.
  - Display clear confirmation dialogs for irreversible actions.

---

## Considerations

- Ensure alignment with other sections of the Mycelium project to provide a unified experience.
- Implement load testing to ensure responsiveness under expected user load.

---

This approach ensures a robust, friendly, and intuitive settings page that makes managing personal and farm configurations straightforward while leveraging the full power of the Mycelium platform.

