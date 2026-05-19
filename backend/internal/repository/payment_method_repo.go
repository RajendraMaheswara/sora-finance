package repository

import (
	"context"
	"errors"
	"sora-finance-api/internal/models"

	"github.com/google/uuid"
	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"
)

type PaymentMethodRepository struct {
	db *pgxpool.Pool
}

func NewPaymentMethodRepository(db *pgxpool.Pool) *PaymentMethodRepository {
	return &PaymentMethodRepository{db: db}
}

func (r *PaymentMethodRepository) GetAll(ctx context.Context) ([]models.PaymentMethod, error) {
	rows, err := r.db.Query(ctx, `
		SELECT id, m_payment_method_type_id, description, logo_url, name,
		       created_at, created_by, updated_at, updated_by, deleted_at, deleted_by
		FROM m_payment_methods
		WHERE deleted_at IS NULL
		ORDER BY created_at DESC
	`)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	var items []models.PaymentMethod
	for rows.Next() {
		var item models.PaymentMethod
		err := rows.Scan(
			&item.ID, &item.PaymentMethodTypeID, &item.Description, &item.LogoURL, &item.Name,
			&item.CreatedAt, &item.CreatedBy, &item.UpdatedAt, &item.UpdatedBy, &item.DeletedAt, &item.DeletedBy,
		)
		if err != nil {
			return nil, err
		}
		items = append(items, item)
	}
	return items, nil
}

func (r *PaymentMethodRepository) GetByID(ctx context.Context, id uuid.UUID) (*models.PaymentMethod, error) {
	var item models.PaymentMethod
	err := r.db.QueryRow(ctx, `
		SELECT id, m_payment_method_type_id, description, logo_url, name,
		       created_at, created_by, updated_at, updated_by, deleted_at, deleted_by
		FROM m_payment_methods
		WHERE id = $1 AND deleted_at IS NULL
	`, id).Scan(
		&item.ID, &item.PaymentMethodTypeID, &item.Description, &item.LogoURL, &item.Name,
		&item.CreatedAt, &item.CreatedBy, &item.UpdatedAt, &item.UpdatedBy, &item.DeletedAt, &item.DeletedBy,
	)
	if err != nil {
		if errors.Is(err, pgx.ErrNoRows) {
			return nil, nil
		}
		return nil, err
	}
	return &item, nil
}
