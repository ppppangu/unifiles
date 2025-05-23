# 使用 PostgreSQL 16 基础镜像
FROM postgres:16

# 设置环境变量避免交互式配置
ENV DEBIAN_FRONTEND=noninteractive

# 更换APT源为中科大镜像并处理PostgreSQL专用源
RUN echo "deb http://mirrors.aliyun.com/debian/ bookworm main non-free contrib" > /etc/apt/sources.list && \
    echo "deb-src http://mirrors.aliyun.com/debian/ bookworm main non-free contrib" >> /etc/apt/sources.list && \
    echo "deb http://mirrors.aliyun.com/debian-security/ bookworm-security main" >> /etc/apt/sources.list && \
    echo "deb-src http://mirrors.aliyun.com/debian-security/ bookworm-security main" >> /etc/apt/sources.list && \
    echo "deb http://mirrors.aliyun.com/debian/ bookworm-updates main non-free contrib" >> /etc/apt/sources.list && \
    echo "deb-src http://mirrors.aliyun.com/debian/ bookworm-updates main non-free contrib" >> /etc/apt/sources.list && \
    echo "deb http://mirrors.aliyun.com/debian/ bookworm-backports main non-free contrib" >> /etc/apt/sources.list && \
    echo "deb-src http://mirrors.aliyun.com/debian/ bookworm-backports main non-free contrib" >> /etc/apt/sources.list

# 安装依赖项
RUN apt-get update && \
    apt-get install -y postgresql-16-pgvector && \
    apt-get install -y --no-install-recommends ca-certificates  gcc g++ libc6-dev cmake make git libreadline-dev postgresql-server-dev-16 libpq-dev pkg-config libssl-dev build-essential libcurl4-openssl-dev libkrb5-dev python3 python3-pip python3-dev postgresql-plpython3-16 curl sudo wget bash openssh-server openssh-client iproute2 ansible gdb clang-format python3-jmespath vim jq postgresql-16-cron python3-requests libicu-dev ninja-build locales liblz4-dev libzstd-dev && \
    rm -rf /var/lib/apt/lists/*

# 安装Rust
RUN curl https://mirrors.ustc.edu.cn/rust-static/rustup/rustup-init.sh -sSf | sh -s -- -y
ENV PATH="/root/.cargo/bin:${PATH}"

# 配置Rust使用国内源
RUN mkdir -p /root/.cargo && \
    echo '[source.crates-io]' > /root/.cargo/config && \
    echo 'replace-with = "ustc"' >> /root/.cargo/config && \
    echo '[source.ustc]' >> /root/.cargo/config && \
    echo 'registry = "sparse+https://mirrors.ustc.edu.cn/crates.io-index/"' >> /root/.cargo/config

# 安装pg_rust扩展相关工具
RUN cargo install cargo-pgx --locked

# 安装 pg_mooncake 扩展,可选
# RUN git clone --recurse-submodules https://gitee.com/meidici911/pg_mooncake && \
#     cd pg_mooncake && \
#     git submodule update --init --recursive third_party/duckdb && \
#     cd third_party/duckdb && \
#     mkdir -p build && \
#     cd build && \
#     cmake .. -DCMAKE_BUILD_TYPE=Release -GNinja && \
#     ninja -j$(nproc) && \
#     cd ../../../ && \
#     make release && \
#     make install

# 安装 rum 插件
RUN git clone https://gitee.com/meidici911/rum && \
    cd rum && \
    make USE_PGXS=1 -j$(nproc) && \
    make USE_PGXS=1 install

# 安装 pg_jieba 插件
RUN git clone https://gitee.com/meidici911/pg_jieba && \
    cd pg_jieba && \
    sed -i 's|https://github.com/yanyiwu/cppjieba|https://gitee.com/meidici911/cppjieba|' .gitmodules && \
    git submodule update --init libjieba && \
    cd libjieba && \
    sed -i 's|https://github.com/yanyiwu/limonp.git|https://gitee.com/meidici911/limonp|' .gitmodules && \
    git submodule update --init deps/limonp && \
    cd .. && \
    mkdir build && \
    cd build && \
    cmake -DPostgreSQL_TYPE_INCLUDE_DIR=/usr/include/postgresql/16/server/ .. && \
    make -j$(nproc) && \
    make install

# 安装pg_search插件,aarch64版的，x86的把arm64改成amd64即可
RUN curl -L "https://gitee.com/meidici911/paradedb/releases/download/v0.15.9/postgresql-16-pg-search_0.15.9-1PARADEDB-bookworm_arm64.deb" -o /tmp/pg_search.deb && \
    sudo apt-get install -y /tmp/*.deb

# 安装 pg_http 插件
RUN git clone https://gitee.com/meidici911/pgsql-http && \
    cd pgsql-http && \
    make && \
    make install

# 安装pg_background 插件用于任务队列
RUN git clone https://gitee.com/meidici911/pg_background && \
    cd pg_background && \
    make && \
    make install

# 配置pip使用国内源
RUN pip3 config set global.index-url https://pypi.tuna.tsinghua.edu.cn/simple

# 安装 timescaledb 拓展
# RUN git clone https://gitee.com/meidici911/timescaledb && \
# cd timescaledb && \
# git checkout 2.17.2 && \
# ./bootstrap && \
# cd build && make && \
# make install

# 安装 vectorscale 拓展
RUN cd /tmp && \
    git clone https://gitee.com/meidici911/pgvectorscale && \
    cd pgvectorscale/pgvectorscale && \
    cargo install --locked cargo-pgrx --version $(cargo metadata --format-version 1 | jq -r '.packages[] | select(.name == "pgrx") | .version') && \
    cargo pgrx init --pg16 pg_config && \
    cargo pgrx install --release

# 设置启动命令
CMD ["postgres", "-c", "config_file=/etc/postgresql/postgresql.conf"]