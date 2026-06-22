package repository

import (
	"context"
	"errors"
	"sora-finance-api/internal/auth"
	"sora-finance-api/internal/models"

	"github.com/google/uuid"
	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"
)

type StoreDiscountRepository struct {
	db *pgxpool.Pool
}

func NewStoreDiscountRepository(db *pgxpool.Pool) *StoreDiscountRepository {
	return &StoreDiscountRepository{db: db}
}

func (r *StoreDiscountRepository) GetAll(ctx context.Context) ([]models.StoreDiscount, error) {
	claims, _ := auth.ClaimsFromContext(ctx)
	query := `
		SELECT id, m_store_id, description, is_percentage, name, nominal,
		       created_at, created_by, updated_at, updated_by, deleted_at, deleted_by
		FROM m_store_discounts
		WHERE deleted_at IS NULL`
	var args []interface{}
	if claims != nil && !auth.IsSystemAdmin(claims) {
		query += ` AND m_store_id = $1`
		args = append(args, claims.StoreID)
	}
	query += `
		ORDER BY created_at DESC`
	rows, err := r.db.Query(ctx, query, args...)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	var items []models.StoreDiscount
	for rows.Next() {
		var item models.StoreDiscount
		err := rows.Scan(
			&item.ID, &item.StoreID, &item.Description, &item.IsPercentage, &item.Name, &item.Nominal,
			&item.CreatedAt, &item.CreatedBy, &item.UpdatedAt, &item.UpdatedBy, &item.DeletedAt, &item.DeletedBy,
		)
		if err != nil {
			return nil, err
		}
		items = append(items, item)
	}
	return items, nil
}

func (r *StoreDiscountRepository) GetByID(ctx context.Context, id uuid.UUID) (*models.StoreDiscount, error) {
	var item models.StoreDiscount
	claims, _ := auth.ClaimsFromContext(ctx)
	query := `
		SELECT id, m_store_id, description, is_percentage, name, nominal,
		       created_at, created_by, updated_at, updated_by, deleted_at, deleted_by
		FROM m_store_discounts
		WHERE id = $1 AND deleted_at IS NULL
	`
	args := []interface{}{id}
	if claims != nil && !auth.IsSystemAdmin(claims) {
		query += ` AND m_store_id = $2`
		args = append(args, claims.StoreID)
	}
	err := r.db.QueryRow(ctx, query, args...).Scan(
		&item.ID, &item.StoreID, &item.Description, &item.IsPercentage, &item.Name, &item.Nominal,
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
