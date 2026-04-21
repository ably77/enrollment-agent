package main

import (
	"context"
	"fmt"
	"log"
	"net"
	"os"
	"strings"

	corev3 "github.com/envoyproxy/go-control-plane/envoy/config/core/v3"
	authv3 "github.com/envoyproxy/go-control-plane/envoy/service/auth/v3"
	typev3 "github.com/envoyproxy/go-control-plane/envoy/type/v3"
	"google.golang.org/genproto/googleapis/rpc/status"
	"google.golang.org/grpc"
	"google.golang.org/grpc/codes"
)

// policies maps "role:tier" → []string of allowed models.
var policies map[string][]string

// initPolicies parses the ABAC_POLICIES env var into the policies map.
// Format: role:tier=model1|model2,role:tier=model3
// If unset, loads defaults:
//
//	enrollment-advisor:standard → [gpt-4o-mini]
//	analytics-agent:premium     → [gpt-4o, gpt-4o-mini]
func initPolicies() {
	policies = make(map[string][]string)
	raw := os.Getenv("ABAC_POLICIES")
	if raw == "" {
		policies["enrollment-advisor:standard"] = []string{"gpt-4o-mini"}
		policies["analytics-agent:premium"] = []string{"gpt-4o", "gpt-4o-mini"}
		return
	}
	for _, entry := range strings.Split(raw, ",") {
		parts := strings.SplitN(entry, "=", 2)
		if len(parts) != 2 {
			continue
		}
		key := strings.TrimSpace(parts[0])
		modelList := strings.Split(parts[1], "|")
		for i := range modelList {
			modelList[i] = strings.TrimSpace(modelList[i])
		}
		policies[key] = modelList
	}
}

// checkABAC performs the ABAC decision.
// Returns (allowed, reason, headers) where headers always contains x-abac-decision,
// and on allow also contains x-abac-agent and x-abac-reason.
func checkABAC(headers map[string]string) (bool, string, map[string]string) {
	role, roleOK := headers["x-agent-role"]
	tier, tierOK := headers["x-agent-tier"]
	model, modelOK := headers["x-agent-model"]

	// Check for missing headers in order: role, tier, model
	if !roleOK || role == "" {
		reason := "missing required header: x-agent-role"
		return false, reason, map[string]string{
			"x-abac-decision": "denied",
		}
	}
	if !tierOK || tier == "" {
		reason := "missing required header: x-agent-tier"
		return false, reason, map[string]string{
			"x-abac-decision": "denied",
		}
	}
	if !modelOK || model == "" {
		reason := "missing required header: x-agent-model"
		return false, reason, map[string]string{
			"x-abac-decision": "denied",
		}
	}

	// Look up policy for role:tier
	key := role + ":" + tier
	allowed, exists := policies[key]
	if !exists {
		reason := fmt.Sprintf("no ABAC policy for agent %q (%s)", role, tier)
		return false, reason, map[string]string{
			"x-abac-decision": "denied",
		}
	}

	// Check if model is in the allowed list
	for _, m := range allowed {
		if m == model {
			reason := fmt.Sprintf("agent %q (%s) authorized for model %s", role, tier, model)
			return true, reason, map[string]string{
				"x-abac-decision": "allowed",
				"x-abac-agent":    role,
				"x-abac-reason":   reason,
			}
		}
	}

	reason := fmt.Sprintf("agent %q (%s) not authorized for model %q (allowed: %s)", role, tier, model, strings.Join(allowed, ", "))
	return false, reason, map[string]string{
		"x-abac-decision": "denied",
	}
}

// --------------------------------------------------------------------
// gRPC server
// --------------------------------------------------------------------

type extAuthzServer struct{}

func (s *extAuthzServer) Check(ctx context.Context, req *authv3.CheckRequest) (*authv3.CheckResponse, error) {
	httpReq := req.GetAttributes().GetRequest().GetHttp()
	headers := httpReq.GetHeaders()
	path := httpReq.GetPath()
	method := httpReq.GetMethod()

	log.Printf("[abac-ext-authz] %s %s | role=%s tier=%s model=%s",
		method, path,
		headers["x-agent-role"],
		headers["x-agent-tier"],
		headers["x-agent-model"],
	)

	allowed, reason, extraHeaders := checkABAC(headers)

	if allowed {
		log.Printf("[abac-ext-authz] ALLOWED: %s", reason)
		okHeaders := []*corev3.HeaderValueOption{}
		for k, v := range extraHeaders {
			okHeaders = append(okHeaders, &corev3.HeaderValueOption{
				Header: &corev3.HeaderValue{Key: k, Value: v},
			})
		}
		return &authv3.CheckResponse{
			Status: &status.Status{Code: int32(codes.OK)},
			HttpResponse: &authv3.CheckResponse_OkResponse{
				OkResponse: &authv3.OkHttpResponse{
					Headers: okHeaders,
				},
			},
		}, nil
	}

	log.Printf("[abac-ext-authz] DENIED: %s", reason)
	denyHeaders := []*corev3.HeaderValueOption{
		{
			Header: &corev3.HeaderValue{
				Key:   "x-abac-decision",
				Value: "denied",
			},
		},
	}
	return &authv3.CheckResponse{
		Status: &status.Status{Code: int32(codes.PermissionDenied)},
		HttpResponse: &authv3.CheckResponse_DeniedResponse{
			DeniedResponse: &authv3.DeniedHttpResponse{
				Status: &typev3.HttpStatus{
					Code: typev3.StatusCode_Forbidden,
				},
				Body:    fmt.Sprintf("denied by ABAC: %s", reason),
				Headers: denyHeaders,
			},
		},
	}, nil
}

func main() {
	port := os.Getenv("PORT")
	if port == "" {
		port = "9000"
	}

	initPolicies()

	log.Printf("Loaded ABAC policies:")
	for key, models := range policies {
		log.Printf("  %s -> [%s]", key, strings.Join(models, ", "))
	}

	lis, err := net.Listen("tcp", ":"+port)
	if err != nil {
		log.Fatalf("Failed to listen on port %s: %v", port, err)
	}

	s := grpc.NewServer()
	authv3.RegisterAuthorizationServer(s, &extAuthzServer{})

	log.Printf("ABAC gRPC ext-authz server listening on :%s", port)
	if err := s.Serve(lis); err != nil {
		log.Fatalf("Failed to serve: %v", err)
	}
}
