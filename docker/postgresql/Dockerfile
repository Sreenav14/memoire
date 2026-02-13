FROM postgres:16

# install dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    git \
    postgresql-server-dev-16 \
    clang \ 
    llvm \
    flex \
    bison

# install pgvector
RUN git clone --branch v0.7.4 https://github.com/pgvector/pgvector.git \
    && cd pgvector \
    && make \
    && make install

# install age
RUN git clone --branch release/PG16/1.5.0 https://github.com/apache/age.git \
    && cd age \
    && make PG_CONFIG=/usr/lib/postgresql/16/bin/pg_config install