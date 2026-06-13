# Design Spec: Seat Availability Tester UI

We will implement an integrated dual-mode tab dashboard in the existing test file `static/test.html`. This UI will allow developers to test both the Train Schedule API and the new Seat Availability API on their local machine or deployed Render environment.

## User Interface Design

1. **Modern Layout**: 
   - A modern dark/slate themed dashboard using Tailwind CSS and Inter typography.
   - Clean tabbed interface at the top to toggle between:
     - **Train Route Info** (`GET /api/train/<number>`)
     - **Seat Availability** (`GET /api/availability`)
   - Adaptive forms showing relevant inputs based on the selected tab.

2. **Form Parameters for Seat Availability**:
   - `Train Number` (5-digit input)
   - `Source Station Code` (e.g. `PRYJ`)
   - `Destination Station Code` (e.g. `NDLS`)
   - `Journey Date` (input with placeholder `DD-MM-YYYY`, e.g. `25-06-2026`)
   - `Travel Class` (select dropdown: `SL`, `3A`, `2A`, `1A`, `CC`, `3E`, defaulting to `SL`)
   - `Quota` (select dropdown: `GN`, `TQ`, `LD`, `SS`, defaulting to `GN`)

3. **Backend Base URL Config**:
   - A configurable backend host input field (defaulting to relative path `/` so it works seamlessly on local localhost and deployed Render domains out-of-the-box).

4. **Result Presentation**:
   - A beautifully formatted visual overview card showing each scraped date, the seat status (e.g., GNWL, Available), and the ticket price.
   - A scrollable JSON viewer block showing the raw API response for debugging.

5. **Error States**:
   - Clean alert badges in red when requests fail (e.g., network failure, validation errors).
