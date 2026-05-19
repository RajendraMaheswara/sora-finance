package models

import (
	"time"

	"github.com/google/uuid"
)

type PaymentMethod struct {
	ID                  uuid.UUID  `json:"id"`
	PaymentMethodTypeID int64      `json:"m_payment_method_type_id"`
	Description         *string    `json:"description,omitempty"`
	LogoURL             *string    `json:"logo_url,omitempty"`
	Name                string     `json:"name"`
	CreatedAt           time.Time  `json:"created_at"`
	CreatedBy           uuid.UUID  `json:"created_by"`
	UpdatedAt           *time.Time `json:"updated_at,omitempty"`
	UpdatedBy           *uuid.UUID `json:"updated_by,omitempty"`
	DeletedAt           *time.Time `json:"deleted_at,omitempty"`
	DeletedBy           *uuid.UUID `json:"deleted_by,omitempty"`
}
