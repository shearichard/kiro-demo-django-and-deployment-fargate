# Deploying to AWS Fargate with Amazon RDS PostgreSQL

This guide walks through deploying the Django Survey app to AWS Fargate with an RDS PostgreSQL database backend. It assumes you have an AWS account and the AWS CLI installed and configured.

---

## Overview of what you'll create

- An ECR repository to store your Docker image
- An RDS PostgreSQL instance as the database
- A Secrets Manager secret to hold sensitive config
- An ECS cluster running on Fargate
- An Application Load Balancer (ALB) to route public traffic to your container

---

## Step 1: Push your Docker image to ECR

Amazon ECR (Elastic Container Registry) is where AWS pulls your image from when starting Fargate tasks.

Create a repository:

```bash
aws ecr create-repository --repository-name django-survey-app --region <your-region>
```

Note the `repositoryUri` in the output — you'll need it below (it looks like `123456789.dkr.ecr.eu-west-1.amazonaws.com/django-survey-app`).

Authenticate Docker to ECR:

```bash
aws ecr get-login-password --region <your-region> | \
  docker login --username AWS --password-stdin <account-id>.dkr.ecr.<your-region>.amazonaws.com
```

Build and push:

```bash
docker build -t django-survey-app .
docker tag django-survey-app:latest <repositoryUri>:latest
docker push <repositoryUri>:latest
```

---

## Step 2: Create the RDS PostgreSQL instance

In the AWS Console, go to RDS and create a new database:

- Engine: PostgreSQL (version 16 recommended to match local dev)
- Template: Free tier is fine for a demo
- DB instance identifier: `django-survey-db`
- Master username: `survey`
- Master password: choose a strong password and note it down
- Initial database name: `survey`
- VPC: use the default VPC, or a custom one — just make sure your Fargate tasks will be in the same VPC
- Public access: set to No (Fargate will connect privately within the VPC)

Once created, note the endpoint hostname (e.g. `django-survey-db.xxxx.eu-west-1.rds.amazonaws.com`).

---

## Step 3: Store secrets in AWS Secrets Manager

Rather than putting sensitive values directly in the ECS task definition, store them in Secrets Manager.

Create a secret with the following key/value pairs:

```
SECRET_KEY        <a long random string, 50+ characters>
DATABASE_URL      postgres://survey:<password>@<rds-endpoint>:5432/survey
```

You can do this in the AWS Console under Secrets Manager, or via CLI:

```bash
aws secretsmanager create-secret \
  --name django-survey-secrets \
  --secret-string '{"SECRET_KEY":"<value>","DATABASE_URL":"postgres://survey:<password>@<rds-endpoint>:5432/survey"}'
```

Note the secret ARN — you'll reference it in the task definition.

---

## Step 4: Create an ECS cluster

In the AWS Console, go to ECS and create a new cluster:

- Cluster name: `django-survey-cluster`
- Infrastructure: AWS Fargate (serverless)

---

## Step 5: Create an ECS task definition

In ECS, create a new task definition:

- Launch type: Fargate
- Task role: create or select an IAM role that has permission to read your Secrets Manager secret
- Task execution role: use the standard `ecsTaskExecutionRole` (create it if it doesn't exist — AWS provides a managed policy for it)
- CPU: 256 (.25 vCPU) is sufficient for a demo
- Memory: 512 MB

Add a container:

- Name: `web`
- Image: `<repositoryUri>:latest`
- Port mappings: container port 8000
- Environment variables — add the following, sourcing sensitive ones from Secrets Manager:
  - `SECRET_KEY` — from Secrets Manager (the ARN you noted above, key `SECRET_KEY`)
  - `DATABASE_URL` — from Secrets Manager (key `DATABASE_URL`)
  - `DEBUG` — value `False`
  - `ALLOWED_HOSTS` — value: your ALB DNS name or custom domain (e.g. `my-survey-alb-123.eu-west-1.elb.amazonaws.com`)
  - `CONN_MAX_AGE` — value `60`

Health check:
- Command: `CMD-SHELL, curl -f http://localhost:8000/health/ || exit 1`
- Interval: 30s, timeout: 5s, retries: 3

---

## Step 6: Create the Application Load Balancer

In the EC2 Console under Load Balancers, create an ALB:

- Scheme: Internet-facing
- Listeners: HTTP on port 80 (add HTTPS on 443 later if you have a certificate)
- VPC and subnets: select at least two availability zones
- Security group: allow inbound HTTP (port 80) from 0.0.0.0/0

Create a target group:

- Target type: IP (required for Fargate)
- Protocol: HTTP, port 8000
- Health check path: `/health/`
- Healthy threshold: 2, unhealthy threshold: 3

Register no targets manually — ECS will do this automatically when the service starts.

---

## Step 7: Configure security groups

You need two security groups:

**ALB security group** (already created above): allows inbound 80/443 from the internet.

**Fargate tasks security group**: allows inbound port 8000 from the ALB security group only (not the open internet). Also allow outbound to the RDS security group on port 5432.

**RDS security group**: allows inbound port 5432 from the Fargate tasks security group only.

This ensures traffic flows: Internet → ALB → Fargate → RDS, with no direct public access to the database or containers.

---

## Step 8: Create the ECS service

In your ECS cluster, create a new service:

- Launch type: Fargate
- Task definition: select the one you created in Step 5
- Service name: `django-survey-service`
- Desired tasks: 1 (increase later if needed)
- VPC and subnets: same VPC as RDS, select private subnets if available
- Security group: the Fargate tasks security group from Step 7
- Load balancer: select the ALB and target group from Step 6

When the service starts, Fargate will pull your image from ECR, run `entrypoint.sh` (which runs `migrate --noinput` then starts gunicorn), and register the task with the ALB target group. The ALB will start health checking `/health/` and begin routing traffic once the task is healthy.

---

## Step 9: Create the Django superuser

Once the service is running, you need to create an admin user. Use ECS Exec to run a command inside the running container:

First, enable ECS Exec on your service (if not already enabled) and ensure the task role has the `ssmmessages` permissions. Then:

```bash
aws ecs execute-command \
  --cluster django-survey-cluster \
  --task <task-id> \
  --container web \
  --interactive \
  --command "python manage.py createsuperuser"
```

---

## Step 10: Access the app

Your app will be available at the ALB DNS name shown in the EC2 Console under Load Balancers, e.g.:

```
http://my-survey-alb-123456.eu-west-1.elb.amazonaws.com/admin/
```

---

## Updating the app

When you push a new image to ECR, force a new deployment to pick it up:

```bash
docker build -t django-survey-app .
docker tag django-survey-app:latest <repositoryUri>:latest
docker push <repositoryUri>:latest

aws ecs update-service \
  --cluster django-survey-cluster \
  --service django-survey-service \
  --force-new-deployment
```

ECS will start a new task with the updated image, wait for it to pass health checks, then drain and stop the old task — zero downtime rolling update.
