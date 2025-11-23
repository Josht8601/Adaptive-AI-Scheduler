# Use a basic Python image with version 3.11.7as the starting environment
FROM python:3.11-slim

# Set a directory inside the container called /app
WORKDIR /app

# Copy the requirements.txt file to install any needed packages
COPY requirements.txt requirements.txt

# Install the packages listed in requirements.txt
RUN pip install -r requirements.txt

# Copy the rest of the files (your StreamLit app code) into the container
COPY . .

# Open ports for StreamLit and Prometheus metrics
EXPOSE 7860
EXPOSE 8000

# Command to run your StreamLit app
#CMD ["python", "app.py"]
CMD ["streamlit", "run", "app.py", "--server.port=7860", "--server.address=0.0.0.0"]