package models

import (
	"time"

	"github.com/google/uuid"
)

type StoreOperationalHour struct {
	ID        uuid.UUID  `json:"id"`
	StoreID   uuid.UUID  `json:"m_store_id"`
	CloseTime *time.Time `json:"close_time,omitempty"`
	DayOfWeek int64      `json:"day_of_week"`
	IsActive  bool       `json:"is_active"`
	OpenTime  *time.Time `json:"open_time,omitempty"`
	CreatedAt time.Time  `json:"created_at"`
	CreatedBy uuid.UUID  `json:"created_by"`
	UpdatedAt *time.Time `json:"updated_at,omitempty"`
	UpdatedBy *uuid.UUID `json:"updated_by,omitempty"`
	DeletedAt *time.Time `json:"deleted_at,omitempty"`
	DeletedBy *uuid.UUID `json:"deleted_by,omitempty"`
}
