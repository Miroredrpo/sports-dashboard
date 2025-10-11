# How to Set Up and Manage the Dynamic Sports Week App

This guide provides a comprehensive overview of how to set up, run, manage, and extend the Sports Week application.

---

## 1. Local Development Setup

Follow these steps to get the application running on your local machine.

### Prerequisites

*   Python 3.8+ and `pip`
*   A free [Supabase](https://supabase.com/) account
*   A free [Render](https://render.com/) or [Vercel](https://vercel.com/) account for deployment

### Setup Steps

1.  **Create a Supabase Project:**
    *   Go to your Supabase dashboard and create a new project.
    *   Save your project's **URL**, **anon key**, and **service role key**. You'll need these for the environment variables.

2.  **Run the Database Schema:**
    *   In your Supabase project, navigate to the **SQL Editor**.
    *   Open the `sports_week_app/sql/schema.sql` file from this repository, copy its content, paste it into the SQL editor, and click **Run**. This will create all the necessary tables.
    *   (Optional) You can also run the `sports_week_app/sql/seed.sql` to pre-populate the four houses.

3.  **Configure Environment Variables:**
    *   In the `sports_week_app` directory, create a new file named `.env`.
    *   Copy the content from `.env.example` and fill in the values from your Supabase project:
        ```
        SUPABASE_URL="your-supabase-url"
        SUPABASE_ANON_KEY="your-supabase-anon-key"
        SUPABASE_SERVICE_ROLE_KEY="your-supabase-service-role-key"
        FLASK_SECRET_KEY="a-strong-and-secret-key"
        ```

4.  **Install Dependencies and Run the App:**
    *   Open your terminal, navigate to the root of the project, and install the required Python packages:
        ```bash
        pip install -r requirements.txt
        ```
    *   Run the Flask application:
        ```bash
        flask run --app sports_week_app/app:app
        ```
    *   The application should now be running at `http://127.0.0.1:5000`.

---

## 2. Admin: Day-to-Day Operations

### How to Add Admins/Teachers

1.  **Sign up a new user** in the application.
2.  Go to your **Supabase dashboard**.
3.  Navigate to **Authentication -> Users** to find the `UUID` of the new user.
4.  Go to **Table Editor** and select the `admins` or `teachers` table.
5.  Click **Insert row**, and paste the user's `UUID` into the `user_id` field. The user will now have the assigned role.

### How to Import Students via CSV

1.  Log in as an admin and navigate to **Admin -> Import Students**.
2.  Prepare a CSV file with the headers: `full_name`, `roll_no`, `house`, and optionally `email`. A sample file is available at `samples/students_sample.csv`.
3.  Upload the CSV file. The application will show a preview, highlighting any invalid rows or duplicates.
4.  Review the data and click **Commit Import**.

---

## 3. Extending the App / Developer Guide

### Code Layout

*   `sports_week_app/app.py`: The main Flask application file containing all routes and backend logic.
*   `sports_week_app/templates/`: Contains all HTML templates.
*   `sports_week_app/static/`: For CSS, JavaScript, and other static assets.
*   `sports_week_app/sql/`: Contains the database schema and seed scripts.

### How Scoring Works

The scoring logic is primarily handled in the `submit_individual_scores` and `submit_group_scores` routes in `app.py`. When scores are submitted, new rows are inserted into the `scores` table, and a corresponding entry is made in the `audit_log` table.

---

## 4. Deployment to Render

1.  **Create a GitHub Repo:** Push your code to a new GitHub repository.
2.  **Create a New Web Service on Render:**
    *   On your Render dashboard, click **New + -> Web Service**.
    *   Connect your GitHub repository.
3.  **Configure the Service:**
    *   **Build Command:** `pip install -r requirements.txt`
    *   **Start Command:** `gunicorn 'sports_week_app.app:app'`
4.  **Add Environment Variables:**
    *   Under the **Environment** tab, add the same key-value pairs from your local `.env` file (`SUPABASE_URL`, `SUPABASE_ANON_KEY`, etc.).
5.  **Deploy:** Click **Create Web Service**. Render will automatically build and deploy your application.

---

## 5. Deployment to Vercel

Vercel is primarily designed for serverless functions, and deploying a traditional Flask app requires a `vercel.json` configuration file to correctly handle the WSGI application.

1.  **Add a `vercel.json` file** to the root of your project:
    ```json
    {
      "builds": [
        {
          "src": "sports_week_app/app.py",
          "use": "@vercel/python"
        }
      ],
      "routes": [
        {
          "src": "/(.*)",
          "dest": "sports_week_app/app.py"
        }
      ]
    }
    ```
2.  **Push to GitHub** and import the project into Vercel. Vercel should automatically detect the Python environment.
3.  **Add Environment Variables** in the Vercel project settings.

This will set up your Flask app to run as a serverless function on Vercel.
