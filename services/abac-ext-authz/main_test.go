package main

import (
	"os"
	"strings"
	"testing"
)

func TestParsePolicies(t *testing.T) {
	// Set a custom ABAC_POLICIES env var and verify parsing
	os.Setenv("ABAC_POLICIES", "enrollment-advisor:standard=gpt-4o-mini,analytics-agent:premium=gpt-4o|gpt-4o-mini")
	defer os.Unsetenv("ABAC_POLICIES")

	initPolicies()

	if got, ok := policies["enrollment-advisor:standard"]; !ok {
		t.Fatal("expected enrollment-advisor:standard in policies")
	} else if len(got) != 1 || got[0] != "gpt-4o-mini" {
		t.Errorf("enrollment-advisor:standard: expected [gpt-4o-mini], got %v", got)
	}

	if got, ok := policies["analytics-agent:premium"]; !ok {
		t.Fatal("expected analytics-agent:premium in policies")
	} else if len(got) != 2 || got[0] != "gpt-4o" || got[1] != "gpt-4o-mini" {
		t.Errorf("analytics-agent:premium: expected [gpt-4o gpt-4o-mini], got %v", got)
	}
}

func TestParsePoliciesDefault(t *testing.T) {
	os.Unsetenv("ABAC_POLICIES")

	initPolicies()

	if got, ok := policies["enrollment-advisor:standard"]; !ok {
		t.Fatal("expected enrollment-advisor:standard in default policies")
	} else if len(got) != 1 || got[0] != "gpt-4o-mini" {
		t.Errorf("enrollment-advisor:standard default: expected [gpt-4o-mini], got %v", got)
	}

	if got, ok := policies["analytics-agent:premium"]; !ok {
		t.Fatal("expected analytics-agent:premium in default policies")
	} else if len(got) != 2 || got[0] != "gpt-4o" || got[1] != "gpt-4o-mini" {
		t.Errorf("analytics-agent:premium default: expected [gpt-4o gpt-4o-mini], got %v", got)
	}
}

func TestCheckABAC(t *testing.T) {
	os.Unsetenv("ABAC_POLICIES")
	initPolicies()

	tests := []struct {
		name          string
		headers       map[string]string
		wantAllowed   bool
		wantReasonSub string // substring of reason
		wantDecision  string // x-abac-decision header value
	}{
		{
			name: "allowed enrollment-advisor standard gpt-4o-mini",
			headers: map[string]string{
				"x-agent-role":  "enrollment-advisor",
				"x-agent-tier":  "standard",
				"x-agent-model": "gpt-4o-mini",
			},
			wantAllowed:   true,
			wantReasonSub: "enrollment-advisor",
			wantDecision:  "allowed",
		},
		{
			name: "allowed analytics-agent premium gpt-4o",
			headers: map[string]string{
				"x-agent-role":  "analytics-agent",
				"x-agent-tier":  "premium",
				"x-agent-model": "gpt-4o",
			},
			wantAllowed:   true,
			wantReasonSub: "analytics-agent",
			wantDecision:  "allowed",
		},
		{
			name: "allowed analytics-agent premium gpt-4o-mini",
			headers: map[string]string{
				"x-agent-role":  "analytics-agent",
				"x-agent-tier":  "premium",
				"x-agent-model": "gpt-4o-mini",
			},
			wantAllowed:   true,
			wantReasonSub: "analytics-agent",
			wantDecision:  "allowed",
		},
		{
			name: "denied enrollment-advisor standard gpt-4o (model not allowed)",
			headers: map[string]string{
				"x-agent-role":  "enrollment-advisor",
				"x-agent-tier":  "standard",
				"x-agent-model": "gpt-4o",
			},
			wantAllowed:   false,
			wantReasonSub: "not authorized",
			wantDecision:  "denied",
		},
		{
			name: "denied unknown role",
			headers: map[string]string{
				"x-agent-role":  "unknown-agent",
				"x-agent-tier":  "standard",
				"x-agent-model": "gpt-4o-mini",
			},
			wantAllowed:   false,
			wantReasonSub: "no ABAC policy",
			wantDecision:  "denied",
		},
		{
			name: "denied missing role header",
			headers: map[string]string{
				"x-agent-tier":  "standard",
				"x-agent-model": "gpt-4o-mini",
			},
			wantAllowed:   false,
			wantReasonSub: "missing required header: x-agent-role",
			wantDecision:  "denied",
		},
		{
			name: "denied missing tier header",
			headers: map[string]string{
				"x-agent-role":  "enrollment-advisor",
				"x-agent-model": "gpt-4o-mini",
			},
			wantAllowed:   false,
			wantReasonSub: "missing required header: x-agent-tier",
			wantDecision:  "denied",
		},
		{
			name: "denied missing model header",
			headers: map[string]string{
				"x-agent-role": "enrollment-advisor",
				"x-agent-tier": "standard",
			},
			wantAllowed:   false,
			wantReasonSub: "missing required header: x-agent-model",
			wantDecision:  "denied",
		},
	}

	for _, tc := range tests {
		t.Run(tc.name, func(t *testing.T) {
			allowed, reason, extraHeaders := checkABAC(tc.headers)

			if allowed != tc.wantAllowed {
				t.Errorf("allowed: got %v, want %v (reason: %s)", allowed, tc.wantAllowed, reason)
			}

			if tc.wantReasonSub != "" {
				if !strings.Contains(reason, tc.wantReasonSub) {
					t.Errorf("reason %q does not contain %q", reason, tc.wantReasonSub)
				}
			}

			if tc.wantDecision != "" {
				decision, ok := extraHeaders["x-abac-decision"]
				if !ok {
					t.Errorf("x-abac-decision header missing from extraHeaders")
				} else if decision != tc.wantDecision {
					t.Errorf("x-abac-decision: got %q, want %q", decision, tc.wantDecision)
				}
			}
		})
	}
}
