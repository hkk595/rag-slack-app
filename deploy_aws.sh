#!/bin/bash

# AWS ECR Deployment Script for Slack RAG Bot
# This script builds a Docker image and pushes it to Amazon ECR

set -e  # Exit on error

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Default values
DEFAULT_REGION="us-east-1"
DEFAULT_REPO_NAME="rag-slack-bot"
DEFAULT_TAG="latest"

# Parse command line arguments
AWS_REGION="${1:-$DEFAULT_REGION}"
REPO_NAME="${2:-$DEFAULT_REPO_NAME}"
IMAGE_TAG="${3:-$DEFAULT_TAG}"
AWS_ACCOUNT_ID="${AWS_ACCOUNT_ID:-}"

# Construct ECR repository URI
ECR_REGISTRY="${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com"
ECR_URI="${ECR_REGISTRY}/${REPO_NAME}"

# Docker variables
DOCKER_PLATFORM="linux/amd64"

# Function to print colored messages
print_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Function to check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Display usage information
usage() {
    echo "Usage: $0 [AWS_REGION] [ECR_REPO_NAME] [IMAGE_TAG]"
    echo ""
    echo "Arguments:"
    echo "  AWS_REGION      AWS region for ECR (default: $DEFAULT_REGION)"
    echo "  ECR_REPO_NAME   Name of ECR repository (default: $DEFAULT_REPO_NAME)"
    echo "  IMAGE_TAG       Docker image tag (default: $DEFAULT_TAG)"
    echo ""
    echo "Environment Variables:"
    echo "  AWS_ACCOUNT_ID  Your AWS account ID (optional, will be auto-detected)"
    echo ""
    echo "Example:"
    echo "  $0 us-west-1 rag-slack-bot v1.0.0"
    echo ""
    exit 1
}

# Check for help flag
if [[ "$1" == "-h" ]] || [[ "$1" == "--help" ]]; then
    usage
fi

print_info "Starting deployment to AWS ECR..."
print_info "Region: $AWS_REGION"
print_info "Repository: $REPO_NAME"
print_info "Tag: $IMAGE_TAG"
echo ""

# Check prerequisites
print_info "Checking prerequisites..."

if ! command_exists aws; then
    print_error "AWS CLI is not installed. Please install it first:"
    print_error "  https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html"
    exit 1
fi

if ! command_exists docker; then
    print_error "Docker is not installed. Please install it first:"
    print_error "  https://docs.docker.com/get-docker/"
    exit 1
fi

# Check if Docker daemon is running
if ! docker info >/dev/null 2>&1; then
    print_error "Docker daemon is not running. Please start Docker."
    exit 1
fi

# Get AWS account ID if not set
if [ -z "$AWS_ACCOUNT_ID" ]; then
    print_info "Getting AWS account ID..."
    AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text 2>/dev/null)
    if [ -z "$AWS_ACCOUNT_ID" ]; then
        print_error "Failed to get AWS account ID. Please ensure AWS CLI is configured:"
        print_error "  aws configure"
        exit 1
    fi
fi

print_info "AWS Account ID: $AWS_ACCOUNT_ID"

# Display ECR repository URI
print_info "ECR URI: $ECR_URI"
echo ""

# Authenticate Docker to ECR
print_info "Authenticating Docker to ECR..."
aws ecr get-login-password --region "$AWS_REGION" | docker login --username AWS --password-stdin "${ECR_REGISTRY}"

if [ $? -ne 0 ]; then
    print_error "Failed to authenticate with ECR"
    exit 1
fi

# Check if ECR repository exists, create if not
print_info "Checking if ECR repository exists..."
if ! aws ecr describe-repositories --repository-names "$REPO_NAME" --region "$AWS_REGION" >/dev/null 2>&1; then
    print_warn "Repository '$REPO_NAME' does not exist. Creating it..."
    aws ecr create-repository \
        --repository-name "$REPO_NAME" \
        --region "$AWS_REGION" \
        --image-scanning-configuration scanOnPush=true \
        --encryption-configuration encryptionType=AES256

    if [ $? -eq 0 ]; then
        print_info "Repository created successfully"
    else
        print_error "Failed to create repository"
        exit 1
    fi
else
    print_info "Repository exists"
fi

echo ""

# Build Docker image
print_info "Building Docker image..."
docker build --platform $DOCKER_PLATFORM -t "$REPO_NAME:$IMAGE_TAG" .

if [ $? -ne 0 ]; then
    print_error "Docker build failed"
    exit 1
fi

print_info "Docker image built successfully"
echo ""

# Tag image for ECR
print_info "Tagging image for ECR..."
docker tag "$REPO_NAME:$IMAGE_TAG" "$ECR_URI:$IMAGE_TAG"

# Also tag as 'latest' if not already
if [ "$IMAGE_TAG" != "latest" ]; then
    docker tag "$REPO_NAME:$IMAGE_TAG" "$ECR_URI:latest"
    print_info "Tagged as both '$IMAGE_TAG' and 'latest'"
else
    print_info "Tagged as 'latest'"
fi

echo ""

# Push image to ECR
print_info "Pushing image to ECR..."
docker push "$ECR_URI:$IMAGE_TAG"

if [ $? -ne 0 ]; then
    print_error "Failed to push image to ECR"
    exit 1
fi

# Push 'latest' tag if applicable
if [ "$IMAGE_TAG" != "latest" ]; then
    docker push "$ECR_URI:latest"
fi

echo ""
print_info "✅ Deployment successful!"
echo ""
print_info "Image URI: $ECR_URI:$IMAGE_TAG"
print_info "Latest URI: $ECR_URI:latest"
echo ""
print_info "To pull this image:"
print_info "  docker pull $ECR_URI:$IMAGE_TAG"
echo ""
print_info "To run this container locally:"
print_info "  docker run -p 8080:8080 --env-file .env $ECR_URI:$IMAGE_TAG"
echo ""
