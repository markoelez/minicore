### Prerequisites

```sh
brew install riscv-gnu-toolchain
```

Ensure the toolchain was added to your path:

```sh
export PATH=$PATH:/usr/local/opt/riscv-gnu-toolchain/bin
```

### Installation

1. Install tests

```sh
git clone https://github.com/riscv/riscv-tests
cd riscv-tests
git submodule update --init --recursive
autoconf
./configure
make -j8
make install
cd ..
```
