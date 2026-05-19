package models

import (
	"time"

	"github.com/google/uuid"
)

type Menu struct {
	ID                uuid.UUID  `json:"id"`
	StoreID           uuid.UUID  `json:"m_store_id"`
	MenuCategoryID    uuid.UUID  `json:"m_menu_category_id"`
	StoreRegulationID *uuid.UUID `json:"m_store_regulation_id,omitempty"`
	BackgroundColor   *string    `json:"background_color,omitempty"`
	Cogs              *float64   `json:"cogs,omitempty"`
	Code              string     `json:"code"`
	Description       *string    `json:"description,omitempty"`
	ImageURL          *string    `json:"image_url,omitempty"`
	Name              string     `json:"name"`
	Price             *float64   `json:"price,omitempty"`
	TotalStock        *float64   `json:"total_stock,omitempty"`
	CreatedAt         time.Time  `json:"created_at"`
	CreatedBy         uuid.UUID  `json:"created_by"`
	UpdatedAt         *time.Time `json:"updated_at,omitempty"`
	UpdatedBy         *uuid.UUID `json:"updated_by,omitempty"`
	DeletedAt         *time.Time `json:"deleted_at,omitempty"`
	DeletedBy         *uuid.UUID `json:"deleted_by,omitempty"`
}
