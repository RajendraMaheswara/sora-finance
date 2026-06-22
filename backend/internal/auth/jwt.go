package auth

import (
	"context"
	"crypto/hmac"
	"crypto/sha256"
	"encoding/base64"
	"encoding/json"
	"errors"
	"net/http"
	"strings"
	"sync"
	"time"

	"sora-finance-api/internal/models"

	"github.com/redis/go-redis/v9"
)

var redisClient *redis.Client
var localBlacklist sync.Map // token string -> exp unix seconds; fallback when Redis is not configured

func InitRedis(client *redis.Client) {
	redisClient = client
}

func InvalidateToken(token string, exp time.Time) {
	ttl := time.Until(exp)
	if ttl <= 0 {
		return
	}

	if redisClient != nil {
		_ = redisClient.Set(context.Background(), "blacklist:"+token, "true", ttl).Err()
		return
	}

	// Development/single-instance fallback. This makes logout work locally,
	// but production should use Redis so the blacklist survives restarts and
	// works across multiple backend instances.
	localBlacklist.Store(token, exp.Unix())
}

func isTokenBlacklisted(token string) bool {
	if redisClient != nil {
		val, err := redisClient.Get(context.Background(), "blacklist:"+token).Result()
		return err == nil && val == "true"
	}

	value, ok := localBlacklist.Load(token)
	if !ok {
		return false
	}

	expUnix, ok := value.(int64)
	if !ok || expUnix <= time.Now().Unix() {
		localBlacklist.Delete(token)
		return false
	}

	return true
}

type contextKey string

const claimsContextKey contextKey = "auth_claims"

type Claims struct {
	UserID    string `json:"user_id"`
	StoreID   string `json:"store_id,omitempty"`
	RoleID    string `json:"role_id,omitempty"`
	Username  string `json:"username"`
	Name      string `json:"name"`
	RoleName  string `json:"role_name,omitempty"`
	ExpiresAt int64  `json:"exp"`
}

func GenerateToken(secret string, user *models.AuthUser, ttl time.Duration) (string, error) {
	if strings.TrimSpace(secret) == "" {
		return "", errors.New("JWT_SECRET is not configured")
	}

	storeID := ""
	if user.StoreID != nil {
		storeID = user.StoreID.String()
	}

	roleID := ""
	if user.RoleID != nil {
		roleID = user.RoleID.String()
	}

	roleName := ""
	if user.RoleName != nil {
		roleName = *user.RoleName
	}

	header := map[string]string{
		"alg": "HS256",
		"typ": "JWT",
	}
	claims := Claims{
		UserID:    user.ID.String(),
		StoreID:   storeID,
		RoleID:    roleID,
		Username:  user.Username,
		Name:      user.Name,
		RoleName:  roleName,
		ExpiresAt: time.Now().Add(ttl).Unix(),
	}

	headerJSON, err := json.Marshal(header)
	if err != nil {
		return "", err
	}
	claimsJSON, err := json.Marshal(claims)
	if err != nil {
		return "", err
	}

	unsigned := base64.RawURLEncoding.EncodeToString(headerJSON) + "." + base64.RawURLEncoding.EncodeToString(claimsJSON)
	signature := sign(unsigned, secret)
	return unsigned + "." + signature, nil
}

func ParseToken(secret string, token string) (*Claims, error) {
	if strings.TrimSpace(secret) == "" {
		return nil, errors.New("JWT_SECRET is not configured")
	}

	parts := strings.Split(token, ".")
	if len(parts) != 3 {
		return nil, errors.New("invalid token format")
	}

	unsigned := parts[0] + "." + parts[1]
	expectedSignature := sign(unsigned, secret)
	if !hmac.Equal([]byte(expectedSignature), []byte(parts[2])) {
		return nil, errors.New("invalid token signature")
	}

	payloadBytes, err := base64.RawURLEncoding.DecodeString(parts[1])
	if err != nil {
		return nil, errors.New("invalid token payload")
	}

	var claims Claims
	if err := json.Unmarshal(payloadBytes, &claims); err != nil {
		return nil, err
	}
	if claims.ExpiresAt < time.Now().Unix() {
		return nil, errors.New("token expired")
	}

	return &claims, nil
}

func Middleware(secret string) func(http.Handler) http.Handler {
	return func(next http.Handler) http.Handler {
		return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
			authHeader := r.Header.Get("Authorization")
			if !strings.HasPrefix(authHeader, "Bearer ") {
				writeAuthError(w, http.StatusUnauthorized, "missing bearer token")
				return
			}

			token := strings.TrimSpace(strings.TrimPrefix(authHeader, "Bearer "))
			if isTokenBlacklisted(token) {
				writeAuthError(w, http.StatusUnauthorized, "token has been logged out")
				return
			}

			claims, err := ParseToken(secret, token)
			if err != nil {
				writeAuthError(w, http.StatusUnauthorized, err.Error())
				return
			}

			ctx := context.WithValue(r.Context(), claimsContextKey, claims)
			next.ServeHTTP(w, r.WithContext(ctx))
		})
	}
}

func ClaimsFromContext(ctx context.Context) (*Claims, bool) {
	claims, ok := ctx.Value(claimsContextKey).(*Claims)
	return claims, ok
}

func sign(unsigned string, secret string) string {
	mac := hmac.New(sha256.New, []byte(secret))
	mac.Write([]byte(unsigned))
	return base64.RawURLEncoding.EncodeToString(mac.Sum(nil))
}

func writeAuthError(w http.ResponseWriter, code int, message string) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(code)
	_ = json.NewEncoder(w).Encode(map[string]string{"error": message})
}
