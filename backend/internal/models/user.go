package models

import (
	"time"

	"github.com/google/uuid"
)

type User struct {
	ID                      uuid.UUID  `json:"id"`
	StoreID                 *uuid.UUID `json:"m_store_id,omitempty"`
	RoleAccessID            *uuid.UUID `json:"m_role_access_id,omitempty"`
	RoleID                  *uuid.UUID `json:"m_role_id,omitempty"`
	UserVerificationTypeID  *int64     `json:"m_user_verification_type_id,omitempty"`
	Address                 *string    `json:"address,omitempty"`
	AvatarURL               *string    `json:"avatar_url,omitempty"`
	CityOfBirth             *string    `json:"city_of_birth,omitempty"`
	DateOfBirth             *time.Time `json:"date_of_birth,omitempty"`
	Email                   *string    `json:"email,omitempty"`
	EmailVerifiedAt         *time.Time `json:"email_verified_at,omitempty"`
	IsActive                bool       `json:"is_active"`
	IsEmailVerified         bool       `json:"is_email_verified"`
	IsPhoneVerified         bool       `json:"is_phone_verified"`
	Name                    string     `json:"name"`
	NIP                     *string    `json:"nip,omitempty"`
	Password                string     `json:"password,omitempty"` // omit from response
	Phone                   *string    `json:"phone,omitempty"`
	PhoneVerifiedAt         *time.Time `json:"phone_verified_at,omitempty"`
	Username                string     `json:"username"`
	CreatedAt               time.Time  `json:"created_at"`
	CreatedBy               uuid.UUID  `json:"created_by"`
	UpdatedAt               *time.Time `json:"updated_at,omitempty"`
	UpdatedBy               *uuid.UUID `json:"updated_by,omitempty"`
	DeletedAt               *time.Time `json:"deleted_at,omitempty"`
	DeletedBy               *uuid.UUID `json:"deleted_by,omitempty"`
}