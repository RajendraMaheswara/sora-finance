package models

import (
	"time"

	"github.com/google/uuid"
)

type MonthlySummary struct {
	ID                      uuid.UUID  `json:"id"`
	StoreID                 uuid.UUID  `json:"m_store_id"`
	Date                    time.Time  `json:"date"`
	TotalCash               *float64   `json:"total_cash,omitempty"`
	TotalRounding           *float64   `json:"total_rounding,omitempty"`
	TotalDebit              *float64   `json:"total_debit,omitempty"`
	TotalEwallet            *float64   `json:"total_ewallet,omitempty"`
	TotalIncome             *float64   `json:"total_income,omitempty"`
	TotalRegulationOutlet   *float64   `json:"total_regulation_outlet,omitempty"`
	TotalRegulationCustomer *float64   `json:"total_regulation_customer,omitempty"`
	TotalHPP                *float64   `json:"total_hpp,omitempty"`
	TotalDiscount           *float64   `json:"total_discount,omitempty"`
	TotalCostAndExpense     *float64   `json:"total_cost_and_expense,omitempty"`
	TotalNetIncome          *float64   `json:"total_net_income,omitempty"`
	CreatedAt               time.Time  `json:"created_at"`
	CreatedBy               uuid.UUID  `json:"created_by"`
	UpdatedAt               *time.Time `json:"updated_at,omitempty"`
	UpdatedBy               *uuid.UUID `json:"updated_by,omitempty"`
	DeletedAt               *time.Time `json:"deleted_at,omitempty"`
	DeletedBy               *uuid.UUID `json:"deleted_by,omitempty"`
}