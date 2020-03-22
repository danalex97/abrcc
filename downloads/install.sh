DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null && pwd )"
DEPS=$DIR/deps

# install Netflix/vmaf dependecies
sudo apt-get update -qq && \
sudo apt-get install -y \
    pkg-config gfortran libhdf5-dev libfreetype6-dev liblapack-dev \
    python3 \
    python3-dev \
    python3-pip \
    python3-setuptools \
    python3-tk

pip3 install -r requirements.txt

# Installs ffmpeg from source (HEAD) with libaom and libx265, as well as a few
# other common libraries

sudo apt -y install \
  autoconf \
  automake \
  build-essential \
  cmake \
  git \
  libass-dev \
  libfreetype6-dev \
  libsdl2-dev \
  libtheora-dev \
  libtool \
  libva-dev \
  libvdpau-dev \
  libvorbis-dev \
  libxcb1-dev \
  libxcb-shm0-dev \
  libxcb-xfixes0-dev \
  mercurial \
  pkg-config \
  texinfo \
  wget \
  zlib1g-dev \
  yasm \
  libvpx-dev \
  libopus-dev \
  libx264-dev \
  libmp3lame-dev \
  libfdk-aac-dev

# Install libaom from source.
if [ ! -d deps/fdk-acc ]; then
  mkdir -p deps
  pushd deps > /dev/null

  git -C fdk-aac pull 2> /dev/null || git clone --depth 1 https://github.com/mstorsjo/fdk-aac 
  pushd fdk-aac > /dev/null 
  autoreconf -fiv 
  ./configure --prefix="$DEPS/ffmpeg_build" --disable-shared 
  make -j8 
  make install
  popd > /dev/null
  
  popd > /dev/null 
fi

# Install libx265 from source.
if [ ! -d deps/x265 ]; then
  pushd deps > /dev/null
  hg clone https://bitbucket.org/multicoreware/x265 
  pushd x265/build/linux > dev/null
  cmake -G "Unix Makefiles" -DCMAKE_INSTALL_PREFIX="$DEPS/ffmpeg_build" -DENABLE_SHARED:bool=off ../../source
  make 
  make install
  popd > /dev/null
  popd > /dev/null
fi

# Install ffmpeg
pushd deps > /dev/null
if [ ! -d ffmpeg ]; then
    wget -O ffmpeg-snapshot.tar.bz2 https://ffmpeg.org/releases/ffmpeg-snapshot.tar.bz2 
    tar xjvf ffmpeg-snapshot.tar.bz2 
fi
pushd ffmpeg > /dev/null
PKG_CONFIG_PATH="$DEPS/ffmpeg_build/lib/pkgconfig" ./configure \
    --prefix="$DEPS/ffmpeg_build" \
    --pkg-config-flags="--static" \
    --extra-cflags="-I$DEPS/ffmpeg_build/include" \
    --extra-ldflags="-L$DEPS/ffmpeg_build/lib" \
    --extra-libs="-lpthread -lm" \
    --bindir="$HOME/bin" \
    --enable-gpl \
    --enable-libass \
    --enable-libfdk-aac \
    --enable-libmp3lame \
    --enable-libx264 \
    --enable-libx265 \
    --enable-libtheora \
    --enable-libfreetype \
    --enable-libvorbis \
    --enable-libopus \
    --enable-libvpx \
    --enable-libaom \
    --enable-nonfree
make 
make install 
hash -r
popd > /dev/null
popd > /dev/null

# install ninja
if [ ! -d ninja ]; then
    git clone git://github.com/ninja-build/ninja.git

    pushd ninja > /dev/null
    git checkout release 
    python3 configure.py --bootstrap
    popd > /dev/null
fi

# install Netflix/vmaf
if [ ! -d vmaf ]; then 
    git clone git@github.com:Netflix/vmaf.git
    
    pushd vmaf > /dev/null
    make
    popd > /dev/null
fi
