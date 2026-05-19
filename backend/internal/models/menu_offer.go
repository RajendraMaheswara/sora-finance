package models

import (
	"time"

	"github.com/google/uuid"
)

type MenuOffer struct {
	ID                 uuid.UUID  `json:"id"`
	StoreID            uuid.UUID  `json:"m_store_id"`
	StoreRegulationID  *uuid.UUID `json:"m_store_regulation_id,omitempty"`
	ExpiredOfferDate   *time.Time `json:"expired_offer_date,omitempty"`
	ImageURL           *string    `json:"image_url,omitempty"`
	Name               string     `json:"name"`
	Price              *float64   `json:"price,omitempty"`
	StartOfferDate     *time.Time `json:"start_offer_date,omitempty"`
	TermsAndConditions string     `json:"terms_and_conditions"`
	CreatedAt          time.Time  `json:"created_at"`
	CreatedBy          uuid.UUID  `json:"created_by"`
	UpdatedAt          *time.Time `json:"updated_at,omitempty"`
	UpdatedBy          *uuid.UUID `json:"updated_by,omitempty"`
	DeletedAt          *time.Time `json:"deleted_at,omitempty"`
	DeletedBy          *uuid.UUID `json:"deleted_by,omitempty"`
	TotalStock         *float64   `json:"total_stock,omitempty"`
}
