package repository

import (
	"context"
	"errors"
	"sora-finance-api/internal/models"

	"github.com/google/uuid"
	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"
)

type CustomerRepository struct {
	db *pgxpool.Pool
}

func NewCustomerRepository(db *pgxpool.Pool) *CustomerRepository {
	return &CustomerRepository{db: db}
}

func (r *CustomerRepository) GetAll(ctx context.Context) ([]models.Customer, error) {
	rows, err := r.db.Query(ctx, `
		SELECT id, m_store_id, name, phone, created_at, created_by,
		       updated_at, updated_by, deleted_at, deleted_by
		FROM m_customers
		WHERE deleted_at IS NULL
		ORDER BY created_at DESC
	`)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	var customers []models.Customer
	for rows.Next() {
		var c models.Customer
		err := rows.Scan(
			&c.ID, &c.StoreID, &c.Name, &c.Phone,
			&c.CreatedAt, &c.CreatedBy,
			&c.UpdatedAt, &c.UpdatedBy, &c.DeletedAt, &c.DeletedBy,
		)
		if err != nil {
			return nil, err
		}
		customers = append(customers, c)
	}
	return customers, nil
}

func (r *CustomerRepository) GetByID(ctx context.Context, id uuid.UUID) (*models.Customer, error) {
	var c models.Customer
	err := r.db.QueryRow(ctx, `
		SELECT id, m_store_id, name, phone, created_at, created_by,
		       updated_at, updated_by, deleted_at, deleted_by
		FROM m_customers
		WHERE id = $1 AND deleted_at IS NULL
	`, id).Scan(
		&c.ID, &c.StoreID, &c.Name, &c.Phone,
		&c.CreatedAt, &c.CreatedBy,
		&c.UpdatedAt, &c.UpdatedBy, &c.DeletedAt, &c.DeletedBy,
	)
	if err != nil {
		if errors.Is(err, pgx.ErrNoRows) {
			return nil, nil
		}
		return nil, err
	}
	return &c, nil
}