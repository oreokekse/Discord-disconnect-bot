FROM python:3.12-alpine

# Set the working directory inside the container
WORKDIR /app

# Copy the requirements file and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the project files into the image
COPY main.py .
COPY pending_commands.txt .

# Start the container with the bot
CMD ["python", "main.py"]
