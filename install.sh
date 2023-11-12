#!/bin/sh

set -e

password='jetson'

# Record the time this script starts
date

# Get the full dir name of this script
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"

# Keep updating the existing sudo time stamp
sudo -v
while true; do sudo -n true; sleep 120; kill -0 "$$" || exit; done 2>/dev/null &

# Install pip and some python dependencies
echo "\e[104m Install pip and some python dependencies \e[0m"
sudo apt-get update
sudo apt install -y python3-pip python3-setuptools python3-pil python3-smbus python3-matplotlib cmake curl
sudo -H pip3 install --upgrade pip

# Install jtop
echo "\e[100m Install jtop \e[0m"
sudo -H pip3 install jetson-stats 



# Install the pre-built PyTorch pip wheel 
echo "\e[45m Install the pre-built PyTorch pip wheel  \e[0m"
cd
wget -N https://nvidia.box.com/shared/static/fjtbno0vpo676a25cgvuqc1wty0fkkg6.whl -O torch-1.10.0-cp36-cp36m-linux_aarch64.whl 
sudo apt-get install -y python3-pip libopenblas-base libopenmpi-dev 
sudo -H pip3 install Cython==0.29.36
sudo -H pip3 install numpy torch-1.10.0-cp36-cp36m-linux_aarch64.whl

# Install torchvision package
echo "\e[45m Install torchvision package \e[0m"
cd
git clone --branch release/0.11 https://github.com/pytorch/vision torchvision
cd torchvision
sudo apt-get install -y libjpeg-dev zlib1g-dev libpython3-dev libopenblas-dev libavcodec-dev libavformat-dev libswscale-dev
export BUILD_VERSION=0.11.1
sudo -H python3 setup.py install
cd  ../
sudo -H pip3 install pillow

# pip dependencies for pytorch-ssd
echo "\e[45m Install dependencies for pytorch-ssd \e[0m"
sudo -H pip3 install protobuf==3.19.6
sudo -H pip3 install boto3 pandas

# Install the pre-built TensorFlow pip wheel
echo "\e[48;5;202m Install the pre-built TensorFlow pip wheel \e[0m"$ sudo apt-get update
sudo apt-get install -y python3-pip pkg-config
sudo ln -s /usr/include/locale.h /usr/include/xlocale.h
sudo apt install -y libhdf5-serial-dev hdf5-tools libhdf5-dev zlib1g-dev zip libjpeg8-dev liblapack-dev libblas-dev gfortran
sudo pip3 install -U --no-deps numpy==1.19.4 future==0.18.2 mock==3.0.5 keras_preprocessing==1.1.2 keras_applications==1.0.8 gast==0.4.0 protobuf==3.19.6 pybind11 pkgconfig
sudo pip3 install --verbose 'Cython<3'
sudo wget --no-check-certificate https://developer.download.nvidia.com/compute/redist/jp/v461/tensorflow/tensorflow-2.7.0+nv22.1-cp36-cp36m-linux_aarch64.whl
sudo pip3 install --verbose tensorflow-2.7.0+nv22.1-cp36-cp36m-linux_aarch64.whl

# Install TensorFlow models repository
echo "\e[48;5;202m Install TensorFlow models \e[0m"
cd
# install newer cmake
sudo apt-get -y remove cmake
wget -O cmake.tar.gz https://github.com/Kitware/CMake/releases/download/v3.28.0-rc4/cmake-3.28.0-rc4-linux-aarch64.tar.gz
tar -zxvf cmake.tar.gz
cd cmake-3.28.0-rc4-linux-aarch64
sudo cp -rf bin/ doc/ share/ /usr/local/
sudo cp -rf man/* /usr/local/man
sync
hash -r
cd
# install bazel
wget -O bazelisk https://github.com/bazelbuild/bazelisk/releases/download/v1.18.0/bazelisk-linux-arm64
sudo mv bazelisk /usr/local/bin/bazel
sudo chmod +x /usr/local/bin/bazel
# install tensorflow-addons
cd
sudo mv /usr/bin/python /usr/bin/python2
sudo ln -s /usr/bin/python3 /usr/bin/python
git clone -b r0.15 https://github.com/tensorflow/addons.git tensorflow-addons
cd tensorflow-addons
export TF_NEED_CUDA="1"
export TF_CUDA_VERSION="10"
export TF_CUDNN_VERSION="8"
export CUDA_TOOLKIT_PATH="/usr/local/cuda"
export CUDNN_INSTALL_PATH="/usr/lib/aarch64-linux-gnu"
python3 ./configure.py
bazel build build_pip_pkg
bazel-bin/build_pip_pkg artifacts
sudo -H pip3 install artifacts/tensorflow_addons-*.whl
sudo rm /usr/bin/python
sudo mv /usr/bin/python2 /usr/bin/python
# Install TensorFlow models repository
sudo -H pip3 install --ignore-installed httplib2
sudo -H pip3 install --ignore-installed launchpadlib
sudo -H pip3 install --ignore-installed PyYAML
sudo -H pip3 install tf-models-official



# Install traitlets (master, to support the unlink() method)
echo "\e[48;5;172m Install traitlets \e[0m"
sudo -H pip3 install traitlets
#sudo -H python3 -m pip install git+https://github.com/ipython/traitlets@dead2b8cdde5913572254cf6dc70b5a6065b86f8

# Install JupyterLab (lock to 3.2.9, latest stable release on python3.6?)
echo "\e[48;5;172m Install Jupyter Lab 3.2.9 \e[0m"
# install nodejs 16x
sudo apt-get update
sudo apt-get install -y ca-certificates curl gnupg
sudo mkdir -p /etc/apt/keyrings
curl -fsSL https://deb.nodesource.com/gpgkey/nodesource-repo.gpg.key | sudo gpg --dearmor -o /etc/apt/keyrings/nodesource.gpg
echo "deb [signed-by=/etc/apt/keyrings/nodesource.gpg] https://deb.nodesource.com/node_16.x nodistro main" | sudo tee /etc/apt/sources.list.d/nodesource.list
sudo apt-get update
sudo apt-get install nodejs -y

sudo apt install -y libffi-dev libssl1.0-dev 
sudo -H pip3 install jupyter jupyterlab==3.2.9 --verbose
sudo -H jupyter labextension install @jupyter-widgets/jupyterlab-manager

jupyter lab --generate-config
python3 -c "from notebook.auth.security import set_password; set_password('$password', '$HOME/.jupyter/jupyter_notebook_config.json')"


# Install jupyter_clickable_image_widget
echo "\e[42m Install jupyter_clickable_image_widget \e[0m"
cd
git clone https://github.com/jaybdub/jupyter_clickable_image_widget
cd jupyter_clickable_image_widget
git checkout tags/v0.1
sudo -H pip3 install -e .
sudo -H jupyter labextension install js
sudo -H jupyter lab build

# fix for permission error
sudo chown -R jetson:jetson /usr/local/share/jupyter/lab/settings/build_config.json

# install version of traitlets with dlink.link() feature
# (added after 4.3.3 and commits after the one below only support Python 3.7+) 
#
sudo -H python3 -m pip install git+https://github.com/ipython/traitlets@dead2b8cdde5913572254cf6dc70b5a6065b86f8
sudo -H jupyter lab build


# =================
# INSTALL jetcam
# =================
cd $HOME
git clone https://github.com/STEM-PLUS-HK/jetcam.git
cd jetcam
sudo -H python3 setup.py install

# =================
# INSTALL torch2trt
# =================
cd 
git clone https://github.com/NVIDIA-AI-IOT/torch2trt 
cd torch2trt 
sudo -H python3 setup.py install --plugins

# =================
# INSTALL jetracer
# =================
cd $HOME
git clone https://github.com/NVIDIA-AI-IOT/jetracer
cd jetracer
sudo -H python3 setup.py install

# ========================================
# Install other misc packages for trt_pose
# ========================================
sudo -H pip3 install tqdm cython pycocotools 
sudo apt-get install python3-matplotlib
sudo -H pip3 install traitlets
sudo -H pip3 install -U scikit-learn

# ==============================================
# Install other misc packages for point_detector
# ==============================================
sudo -H pip3 install tensorboard
sudo -H pip3 install segmentation-models-pytorch


# Install jetcard
echo "\e[44m Install jetcard \e[0m"
cd $DIR
pwd
sudo apt-get install python3-pip python3-setuptools python3-pil python3-smbus
sudo -H pip3 install flask
sudo -H python3 setup.py install

# Install jetcard display service
echo "\e[44m Install jetcard display service \e[0m"
python3 -m jetcard.create_display_service
sudo mv jetcard_display.service /etc/systemd/system/jetcard_display.service
sudo systemctl enable jetcard_display
sudo systemctl start jetcard_display

# Install jetcard jupyter service
echo "\e[44m Install jetcard jupyter service \e[0m"
python3 -m jetcard.create_jupyter_service
sudo mv jetcard_jupyter.service /etc/systemd/system/jetcard_jupyter.service
sudo systemctl enable jetcard_jupyter
sudo systemctl start jetcard_jupyter

# Make swapfile
echo "\e[46m Make swapfile \e[0m"
cd
if [ ! -f /var/swapfile ]; then
	sudo fallocate -l 4G /var/swapfile
	sudo chmod 600 /var/swapfile
	sudo mkswap /var/swapfile
	sudo swapon /var/swapfile
	sudo bash -c 'echo "/var/swapfile swap swap defaults 0 0" >> /etc/fstab'
else
	echo "Swapfile already exists"
fi



# Install remaining dependencies for projects
echo "\e[104m Install remaining dependencies for projects \e[0m"
sudo apt-get install python-setuptools



echo "\e[42m All done! \e[0m"

#record the time this script ends
date

