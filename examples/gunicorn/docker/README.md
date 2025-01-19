# Deploying MicroPie with Gunicorn Using Docker

This guide explains how to deploy the MicroPie framework using Docker and Gunicorn to ensure scalability and portability.


## **1. Prepare Your MicroPie Application**

Ensure your `server.py` file contains the following content:

```python
from MicroPie import Server

class MyApp(Server):
    def index(self, name="Guest"):
        return f"Hello, {name}! Welcome to MicroPie."

# Create an instance of the app
app = MyApp()
```


## **2. Create a `requirements.txt` File**

List the required dependencies:

```
micropie
gunicorn
```


## **3. Create a `Dockerfile`**

Create a `Dockerfile` in the same directory as your `server.py`:

```dockerfile
# Use an official lightweight Python image
FROM python:3.9-slim

# Set the working directory
WORKDIR /app

# Copy application files
COPY server.py requirements.txt ./

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Expose the port the app will run on
EXPOSE 8080

# Start the MicroPie app with Gunicorn
CMD ["gunicorn", "-w", "4", "-b", "0.0.0.0:8080", "server:app"]
```


## **4. Build the Docker Image**

Run the following command to build the Docker image:

```bash
docker build -t micropie-app .
```


## **5. Run the Container**

Start the container with:

```bash
docker run -d -p 8080:8080 --name micropie-container micropie-app
```

Now your app should be accessible at:

```
http://localhost:8080
```


## **6. Viewing Container Logs**

To check the logs and verify if the application is running correctly, use:

```bash
docker logs micropie-container
```


## **7. Stopping and Removing the Container**

To stop the running container:

```bash
docker stop micropie-container
```

To remove the container:

```bash
docker rm micropie-container
```


## **8. Deploying with Docker Compose**

Create a `docker-compose.yml` file:

```yaml
version: '3'
services:
  micropie:
    build: .
    ports:
      - "8080:8080"
    restart: always
```

Start the app using:

```bash
docker-compose up -d
```

Stop it with:

```bash
docker-compose down
```


## **9. Deploying to Cloud Providers**

You can deploy your Docker container to cloud platforms such as:

- AWS ECS (Elastic Container Service)
- Google Cloud Run
- Azure Container Apps
- DigitalOcean App Platform

To push the image to Docker Hub:

1. Log in to Docker Hub:
   ```bash
   docker login
   ```

2. Tag your image:
   ```bash
   docker tag micropie-app your-dockerhub-username/micropie-app:latest
   ```

3. Push to Docker Hub:
   ```bash
   docker push your-dockerhub-username/micropie-app:latest
   ```

Now, the image can be deployed to cloud platforms that support containers.


## **10. Conclusion**

With this setup, your MicroPie application is:

- **Containerized**, making it easy to deploy anywhere.
- **Scalable**, allowing multiple instances to be deployed.
- **Easier to manage**, with isolated dependencies and consistent deployment.

---

For further improvements, consider automating deployments using CI/CD pipelines.


