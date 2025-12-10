# Adaptive AI Scheduler

1. **Project Overview**

   This project focuses on building an Adaptive AI Scheduler that makes everyday planning feel more flexible and realistic. Traditional calendars stay the same even when plans change, which can make it hard to stay on track. My system identifies which events are fixed and which tasks can be moved, and it automatically reorganizes the schedule when something is missed. It uses constraint based optimization and simple forecasting to update the calendar in real time while still respecting the user’s preferences and time windows. The overall goal is to create a scheduling experience that adapts as the day changes and helps reduce stress and improve productivity.

2. **Repository Contents**

   - **src/data/**: data files used to fine-tune pre-trained model Prophet by Facebook
     
   - **src/scheduler/**: The scheduler folder contains the core logic of the Adaptive AI Scheduling Assistant, including the data models, time-slot scoring using Prophet, and the optimization engine powered by OR-Tools. It serves as the backend responsible for generating schedules based on user inputs, preferences, and dynamic constraints.

   - src/scheduler/models.py: Defines the data structures used throughout the system—such as tasks, fixed events, and user preferences—using lightweight Python dataclasses that make the scheduler’s inputs clean, consistent, and easy to work with.

   - src/scheduler/prophet_model.py: Handles the creation of pseudo-historical data, feature engineering, and integration with the pretrained Prophet model to generate utility scores for each time slot based on user preferences and learned patterns.

   - src/scheduler/optimizer.py: Implements the OR-Tools optimization engine that selects the best scheduling arrangement by enforcing constraints, preventing overlaps, and maximizing total utility across all tasks.

   - src/scheduler/scheduler.py: Acts as the orchestration layer that connects Prophet-based scoring with the optimization pipeline, producing the final schedule; it also incorporates additional logic such as missed-event handling and time-based restrictions.
     
   - **src/app.py**: Serves as the interactive Streamlit interface for the Adaptive AI Scheduling Assistant, allowing users to input tasks, fixed events, and preferences while visualizing the generated weekly schedule through a real calendar UI. It connects directly to the backend scheduler, enabling dynamic rescheduling, missed-event handling, and real-time updates based on user interactions.      

   - **src/requirements.txt**: Contains necessary dependencies for running the code for this AI System

   - **deployment/**: The deployment folder contains the configuration and infrastructure files needed to package and run the scheduling assistant in a consistent, containerized environment. It enables smooth local development, testing, and future cloud deployment through Docker and Docker Compose.
  
   - **monitoring/**: Contains configuration files that enable performance and health monitoring of the scheduling assistant when running in a containerized or production environment. It provides the foundation for tracking system metrics, usage patterns, and application behavior over time.
  
   - **notebooks/**: Contains jupyter notebooks used for initial data exploration before getting into model development
  
   - **videos/**: Contains a video demoing the AI Systems functionality
  
   - **documentation/**: Contains all written materials that explain the design, functionality, and development process of the Adaptive AI Scheduling Assistant. It serves as the primary reference for understanding how the system works, how to run it, and the reasoning behind key architectural decisions.

3. **System Entry Point**

   The system’s main entry point is app.py, which launches the Streamlit-based interface for interacting with the Adaptive AI Scheduling Assistant. This interface collects user inputs, displays the weekly calendar, and connects directly to the backend scheduling logic.

   Running the system locally
   - uv run streamlit run app.py

   Running the Application in a Containerized Environment
   - docker-compose up --build
   - Open the UI: http://localhost:7860
     
4. **Video Demonstration**
   - https://youtu.be/-sUlQX7xHqQ

5. **Deployment Strategy**

   **Deployment Method: Docker Containers**

   Docker is used as the primary deployment mechanism for this system. By defining the runtime environment within a Dockerfile, the application can be built into a standardized image that includes the Python         environment, project dependencies, and the Streamlit entry point. This ensures that the application runs reliably across machines without requiring users to manually install dependencies or configure              environments.

   Key benefits of using Docker include:
   - Consistent execution across development, testing, and production systems.
   - Isolation of dependencies to avoid conflicts with host environments.
   - Simplified distribution and versioning of the application image.
   - Compatibility with cloud platforms and orchestration tools.

   The full build and runtime configuration can be found in deployment/Dockerfile.

   **Orchestration with Docker Compose**

   In addition to Docker alone, the system supports deployment through Docker Compose, which automates container setup and makes multi-service deployments easier. Docker Compose is particularly useful as the         project expands to include monitoring services such as Prometheus or additional backend components.

   The docker-compose.yml file handles:
   - Building the application image.
   - Mapping container ports to host ports.
   - Managing container lifecycle with a single command.

   Using Docker Compose also prepares the project for future scaling or integration with services such as databases, API gateways, or monitoring dashboards.

   **Deployment Instructions**

   The following commands summarize how the system is deployed using Docker-based infrastructure:

   - Build the application image: docker build -t ai-scheduler .
   - Run the container: docker run -p 8501:8501 ai-scheduler
   - Start the application using Docker Compose: docker-compose up --build
   - Stop all running containers: docker-compose down

   Once deployed, the application becomes accessible through a web browser at http://localhost:7860.

   **Reference**

   All containerization instructions, scripts, and build configuration details can be found in the deployment directory, specifically in:
   - deployment/Dockerfile
   - deployment/docker-compose.yml

6. **Monitoring and Metrics**

   To ensure reliable operation and gain visibility into system performance, the Adaptive AI Scheduling Assistant incorporates a lightweight monitoring stack based on Prometheus and (optionally) Grafana. These tools provide insight into resource usage, application behavior, and system health, making it easier to diagnose issues, track performance trends, and evaluate the scheduler under different workloads.

   Prometheus
   Prometheus is used as the primary metrics collection tool. It periodically scrapes exposed metrics from the containerized application and stores them in a time-series database. The monitoring configuration—  including scrape intervals and target endpoints—is defined in the monitoring/prometheus.yml file.

   Grafana (Optional)
   Grafana may be added for visualizing Prometheus data through customizable dashboards. Although not required for the core system, Grafana provides a powerful interface for observing trends such as CPU usage, memory consumption, response latency, and model inference times. It can be easily integrated in future deployments.

   Setup Instructions
   - To enable monitoring, the following steps are used:
   - Ensure the Prometheus configuration file (prometheus.yml) is placed inside the monitoring directory. This file defines which endpoints Prometheus will scrape and how often.
   - Add a Prometheus service to a docker-compose.yml file if running in a containerized environment. This typically involves mapping configuration files and exposing the Prometheus port (9090).
   - Run Prometheus alongside the application container so it can scrape metrics from the application’s monitoring endpoint.
   - (Optional) Deploy Grafana through Docker Compose and configure it to read metrics from the Prometheus service. This allows visual dashboards to be created using prebuilt or custom panels.

   When the monitoring stack is running, Prometheus becomes accessible at http://localhost:9090, and Grafana—if enabled—is available at http://localhost:3000.

   The monitoring setup is designed to capture essential performance and system behavior metrics. These may include:
   - CPU utilization: Indicates how heavily the scheduling engine and Prophet model are being used.
   - Memory usage: Helps detect memory leaks or inefficient data handling.
   - Request handling time: Captures how long it takes the system to generate a schedule, useful for evaluating optimization complexity.
   - Container health metrics: Includes uptime, restarts, and resource constraints.
   - Application-level metrics (optional): Custom metrics may be added in future versions, such as how often users trigger re-scheduling, the number of tasks per request, or average optimization time.

   Together, these metrics provide insight into the performance and stability of the scheduling system and form the foundation for future optimization and scaling decisions.

7. **Project Documentation**
   - documentation/AI Systems Project Report.pdf
