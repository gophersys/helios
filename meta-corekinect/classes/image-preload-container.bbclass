# Class for preloading container images

inherit image

# Add native tool dependencies
DEPENDS += "skopeo-native"

# Default to empty list if not defined
CONTAINER_INSECURE_REGISTRIES ??= ""

# Make sure OSTree includes our docker directory
OSTREE_COPY_IMAGE_EXTRA_INCLUDE += " \
    /usr/lib/docker/* \
"

python __anonymous() {
    if not bb.utils.contains('MACHINE_FEATURES', 'preload-containers', True, False, d):
        bb.warn("preload-containers not in MACHINE_FEATURES - containers won't be pulled!")
        return

    images = (d.getVar('CONTAINER_PRELOAD_IMAGES') or "").split()
    if not images:
        bb.warn("No CONTAINER_PRELOAD_IMAGES specified - nothing to pull!")
        return
    
    bb.warn("Will try to pull these images: %s" % images)
}

is_insecure_registry() {
    image="$1"
    for registry in ${CONTAINER_INSECURE_REGISTRIES}; do
        if echo "$image" | grep -q "$registry"; then
            return 0
        fi
    done
    return 1
}

get_image_digest() {
    image="$1"
    if is_insecure_registry "$image"; then
        skopeo inspect --insecure-policy --tls-verify=false docker://${image} | grep -o '"Digest":"[^"]*"' | cut -d'"' -f4 || echo "failed"
    else
        skopeo inspect docker://${image} | grep -o '"Digest":"[^"]*"' | cut -d'"' -f4 || echo "failed"
    fi
}

pull_container_images() {
    if [ -z "${CONTAINER_PRELOAD_IMAGES}" ]; then
        bbwarn "No container images to pull"
        return
    fi

    # Create Docker's image storage directory under /usr
    mkdir -p ${IMAGE_ROOTFS}/usr/lib/docker/images
    export PATH="${STAGING_DIR_NATIVE}/usr/bin:$PATH"

    for image in ${CONTAINER_PRELOAD_IMAGES}; do
        bbwarn "Processing container image: $image"
        
        remote_digest=$(get_image_digest "$image")
        bbwarn "Remote digest for $image: $remote_digest"
        
        archive_name=$(echo "$image" | sed 's|/|-|g' | sed 's|:|--|g')
        archive_path="${IMAGE_ROOTFS}/usr/lib/docker/images/${archive_name}.tar"
        
        if [ -f "$archive_path" ]; then
            local_digest=$(skopeo inspect docker-archive:"$archive_path" | grep -o '"Digest":"[^"]*"' | cut -d'"' -f4 || echo "failed")
            if [ "$remote_digest" = "$local_digest" ] && [ "$remote_digest" != "failed" ]; then
                bbwarn "Image $image already cached with same digest, skipping"
                continue
            fi
            rm -f "$archive_path"
        fi
        
        bbwarn "Pulling image: $image"
        if is_insecure_registry "$image"; then
            bbwarn "Using insecure registry for: $image"
            skopeo copy --insecure-policy --src-tls-verify=false "docker://${image}" "docker-archive:${archive_path}" || bbfatal "Failed to pull $image"
        else
            skopeo copy "docker://${image}" "docker-archive:${archive_path}" || bbfatal "Failed to pull $image"
        fi
        bbwarn "Successfully pulled: $image"
    done

    bbwarn "Current container storage contents:"
    ls -l ${IMAGE_ROOTFS}/usr/lib/docker/images/
}

# Create a new task for container pulling
do_pull_containers() {
    pull_container_images
}

# Add our task to the image generation sequence
addtask do_pull_containers after do_rootfs before do_image

# Ensure container cache is included in the OSTree
OSTREE_COPY_IMAGE_EXTRA_INCLUDE += " \
    /var/cache/containers/* \
" 