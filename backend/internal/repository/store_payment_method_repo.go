package repository

import (
	"context"
	"errors"
	"sora-finance-api/internal/models"

	"github.com/google/uuid"
	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"
)

type StorePaymentMethodRepository struct {
	db *pgxpool.Pool
}

func NewStorePaymentMethodRepository(db *pgxpool.Pool) *StorePaymentMethodRepository {
	return &StorePaymentMethodRepository{db: db}
}

func (r *StorePaymentMethodRepository) GetAll(ctx context.Context) ([]models.StorePaymentMethod, error) {
	rows, err := r.db.Query(ctx, `
		SELECT id, m_store_id, m_payment_method_id, account_name, account_number, description,
		       is_percentage, nominal, qr_code_url, created_at, created_by, updated_at, updated_by,
		       deleted_at, deleted_by
		FROM m_store_payment_methods
		WHERE deleted_at IS NULL
		ORDER BY created_at DESC
	`)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	var items []models.StorePaymentMethod
	for rows.Next() {
		var item models.StorePaymentMethod
		err := rows.Scan(
			&item.ID, &item.StoreID, &item.PaymentMethodID, &item.AccountName, &item.AccountNumber,
			&item.Description, &item.IsPercentage, &item.Nominal, &item.QRCodeURL,
			&item.CreatedAt, &item.CreatedBy, &item.UpdatedAt, &item.UpdatedBy, &item.DeletedAt, &item.DeletedBy,
		)
		if err != nil {
			return nil, err
		}
		items = append(items, item)
	}
	return items, nil
}

func (r *StorePaymentMethodRepository) GetByID(ctx context.Context, id uuid.UUID) (*models.StorePaymentMethod, error) {
	var item models.StorePaymentMethod
	err := r.db.QueryRow(ctx, `
		SELECT id, m_store_id, m_payment_method_id, account_name, account_number, description,
		       is_percentage, nominal, qr_code_url, created_at, created_by, updated_at, updated_by,
		       deleted_at, deleted_by
		FROM m_store_payment_methods
		WHERE id = $1 AND deleted_at IS NULL
	`, id).Scan(
		&item.ID, &item.StoreID, &item.PaymentMethodID, &item.AccountName, &item.AccountNumber,
		&item.Description, &item.IsPercentage, &item.Nominal, &item.QRCodeURL,
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
