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

type StoreOperationalHourRepository struct {
	db *pgxpool.Pool
}

func NewStoreOperationalHourRepository(db *pgxpool.Pool) *StoreOperationalHourRepository {
	return &StoreOperationalHourRepository{db: db}
}

func (r *StoreOperationalHourRepository) GetAll(ctx context.Context) ([]models.StoreOperationalHour, error) {
	claims, _ := auth.ClaimsFromContext(ctx)
	query := `
		SELECT id, m_store_id, close_time, day_of_week, is_active, open_time,
		       created_at, created_by, updated_at, updated_by, deleted_at, deleted_by
		FROM m_store_operational_hours
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

	var items []models.StoreOperationalHour
	for rows.Next() {
		var item models.StoreOperationalHour
		err := rows.Scan(
			&item.ID, &item.StoreID, &item.CloseTime, &item.DayOfWeek, &item.IsActive, &item.OpenTime,
			&item.CreatedAt, &item.CreatedBy, &item.UpdatedAt, &item.UpdatedBy, &item.DeletedAt, &item.DeletedBy,
		)
		if err != nil {
			return nil, err
		}
		items = append(items, item)
	}
	return items, nil
}

func (r *StoreOperationalHourRepository) GetByID(ctx context.Context, id uuid.UUID) (*models.StoreOperationalHour, error) {
	var item models.StoreOperationalHour
	claims, _ := auth.ClaimsFromContext(ctx)
	query := `
		SELECT id, m_store_id, close_time, day_of_week, is_active, open_time,
		       created_at, created_by, updated_at, updated_by, deleted_at, deleted_by
		FROM m_store_operational_hours
		WHERE id = $1 AND deleted_at IS NULL
	`
	args := []interface{}{id}
	if claims != nil && !auth.IsSystemAdmin(claims) {
		query += ` AND m_store_id = $2`
		args = append(args, claims.StoreID)
	}
	err := r.db.QueryRow(ctx, query, args...).Scan(
		&item.ID, &item.StoreID, &item.CloseTime, &item.DayOfWeek, &item.IsActive, &item.OpenTime,
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
