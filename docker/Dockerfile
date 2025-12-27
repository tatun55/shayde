# PlayCap Playwright with Japanese Fonts
FROM mcr.microsoft.com/playwright:v1.48.0-noble

# Install font tools and Japanese fonts
RUN apt-get update && apt-get install -y --no-install-recommends \
    fontconfig \
    fonts-noto-cjk \
    fonts-noto-cjk-extra \
    curl \
    unzip \
    && rm -rf /var/lib/apt/lists/*

# Create font directories
RUN mkdir -p /usr/share/fonts/mac-style /usr/share/fonts/windows-style /usr/share/fonts/custom

# Download Source Han Sans (Adobe) - Mac-style Japanese font
# This is similar to Hiragino Sans
RUN curl -fsSL -o /tmp/source-han-sans.zip \
    "https://github.com/adobe-fonts/source-han-sans/releases/download/2.004R/SourceHanSansJP.zip" && \
    unzip -j /tmp/source-han-sans.zip "OTF/Japanese/*.otf" -d /usr/share/fonts/mac-style/ || \
    unzip -j /tmp/source-han-sans.zip "*.otf" -d /usr/share/fonts/mac-style/ || true && \
    rm -f /tmp/source-han-sans.zip

# Download BIZ UDGothic - Windows-style Japanese font (free from Google Fonts)
RUN curl -fsSL -o /tmp/bizudgothic.zip \
    "https://github.com/googlefonts/morisawa-biz-ud-gothic/releases/download/v1.05/BIZUDGothic.zip" && \
    unzip -j /tmp/bizudgothic.zip "*.ttf" -d /usr/share/fonts/windows-style/ || true && \
    rm -f /tmp/bizudgothic.zip

# Update font cache
RUN fc-cache -fv

# Verify fonts are installed
RUN fc-list | grep -E "(Noto|Source Han|BIZ)" || echo "Some fonts may not be installed"

EXPOSE 3000

CMD ["npx", "playwright", "run-server", "--port", "3000", "--host", "0.0.0.0"]
