package models

import (
	"time"

	"github.com/google/uuid"
)

type StoreDiscount struct {
	ID           uuid.UUID  `json:"id"`
	StoreID      uuid.UUID  `json:"m_store_id"`
	Description  *string    `json:"description,omitempty"`
	IsPercentage bool       `json:"is_percentage"`
	Name         string     `json:"name"`
	Nominal      *float64   `json:"nominal,omitempty"`
	CreatedAt    time.Time  `json:"created_at"`
	CreatedBy    uuid.UUID  `json:"created_by"`
	UpdatedAt    *time.Time `json:"updated_at,omitempty"`
	UpdatedBy    *uuid.UUID `json:"updated_by,omitempty"`
	DeletedAt    *time.Time `json:"deleted_at,omitempty"`
	DeletedBy    *uuid.UUID `json:"deleted_by,omitempty"`
}
