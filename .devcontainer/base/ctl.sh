#!/bin/bash

# Concord DevContainer Control Script
# Usage: ./ctl.sh [build|push|help]

set -euo pipefail

# Configuration
BUILDER_NAME="concord-builder"
BUILDKIT_CONFIG=".devcontainer/buildkitd.toml"
IMAGE_NAME="containers.ad.corekinect.com/concord-devcontainer-base"
DOCKERFILE_PATH=".devcontainer/base/Dockerfile"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Get git information
get_git_info() {
    GIT_BRANCH=$(git branch --show-current)
    GIT_COMMIT=$(git rev-parse HEAD)
    GIT_SHORT_COMMIT=$(git rev-parse --short HEAD)
    
    # Check if working directory is dirty
    if [ $(git status --porcelain | wc -l) -gt 0 ]; then
        GIT_DIRTY="true"
    else
        GIT_DIRTY="false"
    fi
    
    GIT_CREATOR=$(git config user.email)
    
    log_info "Git info: branch=$GIT_BRANCH, commit=$GIT_SHORT_COMMIT, dirty=$GIT_DIRTY, creator=$GIT_CREATOR"
}

# Create buildx builder if it doesn't exist
create_builder() {
    log_info "Checking for buildx builder: $BUILDER_NAME"
    
    if docker buildx ls | grep -q "$BUILDER_NAME"; then
        log_success "Builder '$BUILDER_NAME' already exists"
        docker buildx use "$BUILDER_NAME"
    else
        log_info "Creating new buildx builder: $BUILDER_NAME"
        
        # Ensure buildx directory exists
        mkdir -p ~/.docker/buildx
        
        # Copy buildkit config if it exists
        if [ -f "$BUILDKIT_CONFIG" ]; then
            cp "$BUILDKIT_CONFIG" ~/.docker/buildx/
            log_info "Copied buildkit config from $BUILDKIT_CONFIG"
        fi
        
        # Create the builder
        docker buildx create \
            --name "$BUILDER_NAME" \
            --use \
            --driver docker-container \
            --config ~/.docker/buildx/buildkitd.toml \
            --driver-opt network=host
        
        # Bootstrap the builder
        docker buildx inspect --bootstrap
        
        log_success "Builder '$BUILDER_NAME' created and ready"
    fi
}

# Build for native platform only
build_native() {
    log_info "Building for native platform only"
    
    get_git_info
    create_builder
    
    docker buildx build \
        --build-arg GIT_BRANCH="$GIT_BRANCH" \
        --build-arg GIT_COMMIT="$GIT_COMMIT" \
        --build-arg GIT_DIRTY="$GIT_DIRTY" \
        --build-arg GIT_CREATOR="$GIT_CREATOR" \
        --tag "$IMAGE_NAME:latest" \
        --tag "$IMAGE_NAME:$GIT_SHORT_COMMIT" \
        --load \
        -f "$DOCKERFILE_PATH" .
    
    log_success "Build completed successfully"
    log_info "Images tagged as: $IMAGE_NAME:latest and $IMAGE_NAME:$GIT_SHORT_COMMIT"
}

# Build and push for multiple platforms
build_and_push() {
    log_info "Building and pushing for multiple platforms (linux/amd64,linux/arm64)"
    
    get_git_info
    create_builder
    
    docker buildx build \
        --platform linux/amd64,linux/arm64 \
        --build-arg GIT_BRANCH="$GIT_BRANCH" \
        --build-arg GIT_COMMIT="$GIT_COMMIT" \
        --build-arg GIT_DIRTY="$GIT_DIRTY" \
        --build-arg GIT_CREATOR="$GIT_CREATOR" \
        --tag "$IMAGE_NAME:latest" \
        --tag "$IMAGE_NAME:$GIT_SHORT_COMMIT" \
        --push \
        -f "$DOCKERFILE_PATH" .
    
    log_success "Build and push completed successfully"
    log_info "Images pushed as: $IMAGE_NAME:latest and $IMAGE_NAME:$GIT_SHORT_COMMIT"
}

# Show help
show_help() {
    echo "Concord DevContainer Control Script"
    echo ""
    echo "Usage: $0 [COMMAND]"
    echo ""
    echo "Commands:"
    echo "  build    Build image for native platform only (loads to local Docker)"
    echo "  push     Build and push image for multiple platforms (linux/amd64,linux/arm64)"
    echo "  help     Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0 build     # Build locally for your current platform"
    echo "  $0 push      # Build and push for both AMD64 and ARM64"
    echo ""
    echo "The script will automatically:"
    echo "  - Extract git information (branch, commit, dirty status, creator email)"
    echo "  - Create buildx builder if it doesn't exist"
    echo "  - Apply appropriate build arguments and tags"
}

# Main script logic
main() {
    case "${1:-help}" in
        "build")
            build_native
            ;;
        "push")
            build_and_push
            ;;
        "help"|"-h"|"--help")
            show_help
            ;;
        *)
            log_error "Unknown command: $1"
            echo ""
            show_help
            exit 1
            ;;
    esac
}

# Run main function with all arguments
main "$@"
