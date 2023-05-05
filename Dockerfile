FROM public.ecr.aws/lambda/python:3.8 

# Update package list and install development tools, glibc-static, and libstdc++-static
RUN yum -y update && \
  yum -y groupinstall "Development Tools" && \
  yum -y install glibc-static libstdc++-static

# Build the latest release of stockfish - TODO experiment with the ARCH flag
RUN git clone -b sf_15.1 https://github.com/official-stockfish/Stockfish.git
RUN cd Stockfish/src && \
  LDFLAGS=-static make -j profile-build ARCH=x86-64-modern COMP=gcc && \
  make strip

ENTRYPOINT [ "sh" ]