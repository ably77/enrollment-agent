FROM --platform=$BUILDPLATFORM golang:1.25-alpine AS builder
ARG TARGETARCH
WORKDIR /app
COPY go.mod go.sum ./
RUN go mod download
COPY main.go .
RUN CGO_ENABLED=0 GOOS=linux GOARCH=$TARGETARCH go build -o /abac-ext-authz .

FROM gcr.io/distroless/static-debian12
COPY --from=builder /abac-ext-authz /abac-ext-authz
EXPOSE 9000
ENTRYPOINT ["/abac-ext-authz"]
