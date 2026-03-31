FROM containers.ad.corekinect.com/ncs-build:2.7.0

RUN apt-get update && apt-get install -y --no-install-recommends \
    openssh-client ccache && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY prisma/ prisma/
RUN cd /app && prisma generate --schema=prisma/schema.prisma

COPY src/ src/

ENV PYTHONPATH=/app/src
ENV BUILD_SERVICE_PORT=9002
ENV CCACHE_DIR=/ccache
ENV CCACHE_MAXSIZE=10G
ENV CMAKE_C_COMPILER_LAUNCHER=ccache
ENV CMAKE_CXX_COMPILER_LAUNCHER=ccache
ENV CMAKE_BUILD_PARALLEL_LEVEL=14

EXPOSE 9002

CMD ["python3", "-m", "src.main"]
