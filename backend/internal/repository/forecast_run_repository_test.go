package repository

import "testing"

type forecastRunStatusFixture struct {
	Status string
}

func TestIsSuccessfulForecastRun(t *testing.T) {
	tests := []struct {
		name string
		in   interface{}
		want bool
	}{
		{name: "success", in: forecastRunStatusFixture{Status: "success"}, want: true},
		{name: "success uppercase with spaces", in: forecastRunStatusFixture{Status: " SUCCESS "}, want: true},
		{name: "failed", in: forecastRunStatusFixture{Status: "failed"}, want: false},
		{name: "running", in: forecastRunStatusFixture{Status: "running"}, want: false},
		{name: "missing status", in: struct{}{}, want: false},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			if got := isSuccessfulForecastRun(tt.in); got != tt.want {
				t.Fatalf("isSuccessfulForecastRun() = %v, want %v", got, tt.want)
			}
		})
	}
}
