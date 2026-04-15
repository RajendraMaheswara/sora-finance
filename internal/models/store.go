package models

import (
	"time"

	"github.com/google/uuid"
)

type Store struct {
	ID                   uuid.UUID  `json:"id"`
	SubscriptionTypeID   int64      `json:"m_subscription_type_id"`
	Coins                *int64     `json:"coins,omitempty"`
	ExpiredDate          *time.Time `json:"expired_date,omitempty"`
	IsActive             bool       `json:"is_active"`
	Name                 string     `json:"name"`
	CreatedAt            time.Time  `json:"created_at"`
	CreatedBy            uuid.UUID  `json:"created_by"`
	UpdatedAt            *time.Time `json:"updated_at,omitempty"`
	UpdatedBy            *uuid.UUID `json:"updated_by,omitempty"`
	DeletedAt            *time.Time `json:"deleted_at,omitempty"`
	DeletedBy            *uuid.UUID `json:"deleted_by,omitempty"`
	IsTutorialCompleted  bool       `json:"is_tutorial_completed"`
	TutorialStep         int64      `json:"tutorial_step"`
}