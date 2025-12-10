1. **Project Overview**

   This project focuses on building an Adaptive AI Scheduler that makes everyday planning feel more flexible and realistic. Traditional calendars stay the same even when plans change, which can make it hard to stay on track. My system identifies which events are fixed and which tasks can be moved, and it automatically reorganizes the schedule when something is missed. It uses constraint based optimization and simple forecasting to update the calendar in real time while still respecting the user’s preferences and time windows. The overall goal is to create a scheduling experience that adapts as the day changes and helps reduce stress and improve productivity.

2. **Repository Contents**

   - src/data/: data files used to fine-tune pre-trained model Prophet by Facebook
   - src/scheduler/: The scheduler folder contains the core logic of the Adaptive AI Scheduling Assistant, including the data models, time-slot scoring using Prophet, and the optimization engine powered by OR-Tools. It serves as the backend responsible for generating schedules based on user inputs, preferences, and dynamic constraints.

         - models.py: Defines the data structures used throughout the system—such as tasks, fixed events, and user preferences—using lightweight Python dataclasses that make the scheduler’s inputs clean, consistent, and easy to work with.

         - prophet_model.py: Handles the creation of pseudo-historical data, feature engineering, and integration with the pretrained Prophet model to generate utility scores for each time slot based on user preferences and learned patterns.

         - optimizer.py: Implements the OR-Tools optimization engine that selects the best scheduling arrangement by enforcing constraints, preventing overlaps, and maximizing total utility across all tasks.

         - scheduler.py: Acts as the orchestration layer that connects Prophet-based scoring with the optimization pipeline, producing the final schedule; it also incorporates additional logic such as missed-event handling and time-based restrictions.
     
   - src/app.py: Serves as the interactive Streamlit interface for the Adaptive AI Scheduling Assistant, allowing users to input tasks, fixed events, and preferences while visualizing the generated weekly schedule through a real calendar UI. It connects directly to the backend scheduler, enabling dynamic rescheduling, missed-event handling, and real-time updates based on user interactions.      
   - src/requirements.txt: Contains necessary dependencies for running the code for this AI System

   - deployment/: The deployment folder contains the configuration and infrastructure files needed to package and run the scheduling assistant in a consistent, containerized environment. It enables smooth local development, testing, and future cloud deployment through Docker and Docker Compose.
  
   - monitoring/: Contains configuration files that enable performance and health monitoring of the scheduling assistant when running in a containerized or production environment. It provides the foundation for tracking system metrics, usage patterns, and application behavior over time.
  
   - notebooks/: Contains jupyter notebooks used for initial data exploration before getting into model development
  
   - videos/: Contains a video demoing the AI Systems functionality
  
   - documentation/: Contains all written materials that explain the design, functionality, and development process of the Adaptive AI Scheduling Assistant. It serves as the primary reference for understanding how the system works, how to run it, and the reasoning behind key architectural decisions.
