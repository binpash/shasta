#!/bin/sh

if [ ! -d libdash_tests/ ]; then
  git clone https://github.com/binpash/libdash.git
  mv libdash/test libdash_tests
  rm -rf libdash
fi

pip install ..[dev]

# shfmt >= 3.14.0 is required
SHFMT_VERSION=v3.14.1
SHFMT_SHA256=76e77641faa025814b77f153b29796b8e6fa2fca03e0c76a691608b86c7ea7bf
curl -fsSL -o /tmp/shfmt \
  "https://github.com/mvdan/sh/releases/download/${SHFMT_VERSION}/shfmt_${SHFMT_VERSION}_linux_amd64"
echo "${SHFMT_SHA256}  /tmp/shfmt" | sha256sum -c -
sudo install -m 0755 /tmp/shfmt /usr/local/bin/shfmt
shfmt --version