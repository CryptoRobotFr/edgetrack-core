FROM node:20-alpine

WORKDIR /app

# Install pnpm
RUN corepack enable && corepack prepare pnpm@latest --activate

# Copy dependency files
COPY package.json pnpm-lock.yaml* ./

# Install dependencies
RUN pnpm install --frozen-lockfile || pnpm install

# Copy source files
COPY . .

# Expose port
EXPOSE 3000

# Run the development server
CMD ["pnpm", "dev", "--host", "0.0.0.0", "--port", "3000"]
