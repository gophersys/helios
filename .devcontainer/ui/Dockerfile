FROM containers.ad.corekinect.com/concord-devcontainer-base:latest

# ----------------------------------------------------
#                                      Build Arguments
# ----------------------------------------------------
# Default docker arguments
ARG TARGETPLATFORM
ARG BUILDPLATFORM

# Environment versions
ARG FLUTTER_VERSION=3.35.4

# ----------------------------------------------------
#                                    Prerequisites & Tools
# ----------------------------------------------------
RUN apt update && apt install -y \
  curl \
  git \
  unzip \
  xz-utils \
  zip \
  libglu1-mesa \
  openjdk-17-jdk \
  wget \
  socat \
  lcov \
  clang \
  cmake \
  ninja-build \
  pkg-config \
  --no-install-recommends

# ----------------------------------------------------
#                                             nrfjprog
# ----------------------------------------------------
RUN apt install -y openjdk-11-jdk-headless --no-install-recommends

# ----------------------------------------------------
#                                        Android SDK Setup
# ----------------------------------------------------
# Prepare Android directories and system variables
RUN mkdir -p /opt/android/sdk/cmdline-tools
ENV ANDROID_SDK_ROOT=/opt/android/sdk

# Set up Android SDK
ENV CMDLINE_TOOLS_VERSION=6858069
RUN wget -O sdk-tools.zip https://dl.google.com/android/repository/commandlinetools-linux-${CMDLINE_TOOLS_VERSION}_latest.zip
RUN unzip sdk-tools.zip && rm sdk-tools.zip
RUN mv cmdline-tools /opt/android/sdk/cmdline-tools/latest
ENV PATH="$PATH:$ANDROID_SDK_ROOT/cmdline-tools/latest/bin:$ANDROID_SDK_ROOT/cmdline-tools/tools/bin"
ENV PATH="$PATH:/opt/android/sdk/platform-tools"
RUN yes | sdkmanager --licenses
RUN sdkmanager "build-tools;28.0.3" "build-tools;35.0.1" "platform-tools" "platforms;android-35" "platforms;android-36" "sources;android-35" "sources;android-36"

# ----------------------------------------------------
#                                        Flutter SDK Setup
# ----------------------------------------------------
# Download Flutter SDK beta release
RUN wget -O flutter.tar.xz https://storage.googleapis.com/flutter_infra_release/releases/beta/linux/flutter_linux_3.37.0-0.1.pre-beta.tar.xz
RUN tar xf flutter.tar.xz -C /opt/
RUN rm flutter.tar.xz
ENV PATH="$PATH:/opt/flutter/bin"

# Fix Git ownership issues for Flutter
RUN git config --global --add safe.directory /opt/flutter

# This is part of a workaround mentioned in https://github.com/flutter/flutter/issues/61604#issuecomment-739885494
# ENV ADB_SERVER_SOCKET=tcp:host.docker.internal:5037  # Commented out for WSL2 compatibility

# Pre-download Dart SDK and run basic check
RUN flutter precache
RUN flutter doctor --android-licenses

# Configure Flutter for web development
RUN flutter config --enable-web

# ----------------------------------------------------
#                                    Chrome Setup for Web Development
# ----------------------------------------------------
# Install Google Chrome for web development
RUN wget -q -O - https://dl.google.com/linux/linux_signing_key.pub | apt-key add - \
  && echo "deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main" > /etc/apt/sources.list.d/google-chrome.list \
  && apt update \
  && apt install -y google-chrome-stable --no-install-recommends \
  && rm -rf /var/lib/apt/lists/*

# Set Chrome executable path
ENV CHROME_EXECUTABLE=/usr/bin/google-chrome-stable

# ----------------------------------------------------
#                                    Flutter Tools Setup
# ----------------------------------------------------
# Setup flutterfire cli
RUN dart pub global activate flutterfire_cli
RUN mkdir -p /opt/bin
RUN cd /opt/bin && wget -O firebase https://firebase.tools/bin/linux/latest && chmod +x firebase
ENV PATH="$PATH:/root/.pub-cache/bin"
ENV PATH="$PATH:/opt/bin"

# Setup FVM
RUN dart pub global activate fvm

# This is part of a workaround mentioned in https://github.com/flutter/flutter/issues/61604#issuecomment-739885494
# The dart VM service has problems connecting to the real device by default so we need to use socat to forward the connection.
CMD ["socat", "tcp-listen:10388,bind=127.0.0.1,fork", "tcp:host.docker.internal:10388"] 