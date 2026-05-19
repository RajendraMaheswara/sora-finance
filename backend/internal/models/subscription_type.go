package models

import (
	"time"

	"github.com/google/uuid"
)

type SubscriptionType struct {
	ID          int64      `json:"id"`
	Coins       *int64     `json:"coins,omitempty"`
	Day         *int64     `json:"day,omitempty"`
	Description *string    `json:"description,omitempty"`
	ImageURL    *string    `json:"image_url,omitempty"`
	IsActive    bool       `json:"is_active"`
	MaxUsers    int64      `json:"max_users"`
	Name        string     `json:"name"`
	CreatedAt   time.Time  `json:"created_at"`
	CreatedBy   uuid.UUID  `json:"created_by"`
	UpdatedAt   *time.Time `json:"updated_at,omitempty"`
	UpdatedBy   *uuid.UUID `json:"updated_by,omitempty"`
	DeletedAt   *time.Time `json:"deleted_at,omitempty"`
	DeletedBy   *uuid.UUID `json:"deleted_by,omitempty"`
}
