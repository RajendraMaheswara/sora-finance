package repository

import (
	"context"
	"errors"
	"sora-finance-api/internal/models"

	"github.com/google/uuid"
	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"
)

type SalesDailySummaryRepository struct {
	db *pgxpool.Pool
}

func NewSalesDailySummaryRepository(db *pgxpool.Pool) *SalesDailySummaryRepository {
	return &SalesDailySummaryRepository{db: db}
}

func (r *SalesDailySummaryRepository) GetAll(ctx context.Context) ([]models.SalesDailySummary, error) {
	rows, err := r.db.Query(ctx, `
		SELECT id, m_store_id, date,
		       total_omzet, total_hpp, total_profit, total_discount,
		       total_regulation, total_transaction, total_rounding,
		       created_at, created_by, updated_at, updated_by, deleted_at, deleted_by
		FROM t_sales_daily_summaries
		WHERE deleted_at IS NULL
		ORDER BY date DESC
	`)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	var summaries []models.SalesDailySummary
	for rows.Next() {
		var s models.SalesDailySummary
		err := rows.Scan(
			&s.ID, &s.StoreID, &s.Date,
			&s.TotalOmzet, &s.TotalHpp, &s.TotalProfit, &s.TotalDiscount,
			&s.TotalRegulation, &s.TotalTransaction, &s.TotalRounding,
			&s.CreatedAt, &s.CreatedBy, &s.UpdatedAt, &s.UpdatedBy, &s.DeletedAt, &s.DeletedBy,
		)
		if err != nil {
			return nil, err
		}
		summaries = append(summaries, s)
	}
	return summaries, nil
}

func (r *SalesDailySummaryRepository) GetByID(ctx context.Context, id uuid.UUID) (*models.SalesDailySummary, error) {
	var s models.SalesDailySummary
	err := r.db.QueryRow(ctx, `
		SELECT id, m_store_id, date,
		       total_omzet, total_hpp, total_profit, total_discount,
		       total_regulation, total_transaction, total_rounding,
		       created_at, created_by, updated_at, updated_by, deleted_at, deleted_by
		FROM t_sales_daily_summaries
		WHERE id = $1 AND deleted_at IS NULL
	`, id).Scan(
		&s.ID, &s.StoreID, &s.Date,
		&s.TotalOmzet, &s.TotalHpp, &s.TotalProfit, &s.TotalDiscount,
		&s.TotalRegulation, &s.TotalTransaction, &s.TotalRounding,
		&s.CreatedAt, &s.CreatedBy, &s.UpdatedAt, &s.UpdatedBy, &s.DeletedAt, &s.DeletedBy,
	)
	if err != nil {
		if errors.Is(err, pgx.ErrNoRows) {
			return nil, nil
		}
		return nil, err
	}
	return &s, nil
}