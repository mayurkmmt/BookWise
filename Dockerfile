FROM python:3.10-slim

# Ensure Python output is sent straight to terminal (logs) and no .pyc files are written
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Install system dependencies needed for compiling postgres client and other packages
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Install uv globally
RUN pip install uv

# Copy dependency files
COPY pyproject.toml uv.lock ./

# Use uv to generate a static requirements file from the lockfile, then install system-wide
RUN uv export --no-dev --format requirements-txt > requirements.txt
RUN uv pip install --system -r requirements.txt

# Copy the rest of the application
COPY . /app/

# Expose the standard Django port
EXPOSE 8000

# Default command for development using Django's dev server
CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]
