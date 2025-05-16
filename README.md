# 4-Week Program Tracker

A Streamlit application designed to help users track their 4-week strength and conditioning program. It includes features for logging resistance workouts, mobility sessions, cardio activities, and personal metrics, along with user authentication and data visualization.

## Features

*   **User Authentication:** Secure sign-up and login functionality.
*   **Workout Logging:**
    *   **Resistance Training:** Log exercises, sets, reps, weight, and RIR (Reps In Reserve).
    *   **Mobility:** Track completion of different mobility routines.
    *   **Cardio:** Record type, duration, and average heart rate for cardio sessions.
*   **Profile & Metrics:** Record and track personal metrics like height, weight, age, sex, and body fat percentage.
*   **Data Visualization:** View progress charts for key lifts and personal metrics over time.
*   **Workout Logs:** Access historical data for all logged activities.
*   **Program Guide:** In-app guide detailing the 4-week program framework, weekly template, warm-up rules, and nutrition tips.
*   **Mobile-Friendly UI:** Responsive design for use on various devices.

## Technologies Used

*   Python 3.13+
*   Streamlit
*   Pandas
*   SQLite
*   pytest

## Setup and Installation

1.  **Clone the repository:**
    ```bash
    git clone <your-repository-url>
    cd 4-week-program 
    ```
    *(Replace `<your-repository-url>` with the actual URL of your repository. The directory name `4-week-program` is based on the `name` field in your `pyproject.toml`.)*

2.  **Create and activate a virtual environment:**
    Using `venv`:
    ```bash
    python -m venv .venv
    source .venv/bin/activate  # On Windows: .venv\Scripts\activate
    ```

3.  **Install dependencies:**
    This project uses `uv` for fast dependency management. If you don't have `uv`, install it first (e.g., `pip install uv`).
    Then, install the project dependencies from the project root directory:
    ```bash
    uv pip install -e .
    ```
    This command installs the packages listed in `pyproject.toml` in editable mode.

4.  **Database Initialization:**
    The SQLite database (`workout_tracker.db`) and its tables will be automatically initialized when you first run the application.

## Running the Application

To start the Streamlit application, run the following command from the project's root directory:

```bash
streamlit run app.py
```

The application will open in your default web browser.

## Running Tests

The project uses `pytest` for testing. To run the tests from the project's root directory:

```bash
pytest
```
This will execute tests defined in `test_app.py` and use a separate test database (`test_workout_tracker.db`).
