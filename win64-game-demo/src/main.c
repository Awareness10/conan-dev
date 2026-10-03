// Breakout with particles and screen shake. Arrows/A-D or mouse to move,
// Space or click to launch, R to restart, Esc to quit.
#include <math.h>
#include <raylib.h>

#define W 960
#define H 640
#define COLS 12
#define ROWS 7
#define MAX_PARTICLES 512

typedef struct { Rectangle rect; Color color; bool alive; } Brick;
typedef struct { Vector2 pos, vel; Color color; float life; } Particle;

static Brick bricks[ROWS][COLS];
static Particle particles[MAX_PARTICLES];
static Rectangle paddle;
static Vector2 ball, ballVel;
static bool launched;
static int score, lives, bricksLeft;
static float shake;

static void reset_ball(void) {
    launched = false;
    ball = (Vector2){paddle.x + paddle.width / 2, paddle.y - 10};
    ballVel = (Vector2){0};
}

static void reset_game(void) {
    const float gap = 6, bw = (W - gap * (COLS + 1)) / COLS, bh = 22;
    for (int r = 0; r < ROWS; r++) {
        for (int c = 0; c < COLS; c++) {
            bricks[r][c] = (Brick){
                {gap + c * (bw + gap), 70 + r * (bh + gap), bw, bh},
                ColorFromHSV(r * 360.0f / ROWS, 0.75f, 0.95f), true};
        }
    }
    bricksLeft = ROWS * COLS;
    paddle = (Rectangle){W / 2.0f - 60, H - 40, 120, 14};
    score = 0;
    lives = 3;
    reset_ball();
}

static void burst(Vector2 at, Color color, int count) {
    for (int i = 0, n = 0; i < MAX_PARTICLES && n < count; i++) {
        if (particles[i].life > 0) continue;
        float angle = GetRandomValue(0, 359) * DEG2RAD, speed = GetRandomValue(60, 320);
        particles[i] = (Particle){at, {cosf(angle) * speed, sinf(angle) * speed}, color, 1.0f};
        n++;
    }
}

static void update(float dt) {
    // Paddle: keyboard or mouse.
    float move = (IsKeyDown(KEY_RIGHT) || IsKeyDown(KEY_D)) - (IsKeyDown(KEY_LEFT) || IsKeyDown(KEY_A));
    paddle.x += move * 600 * dt;
    Vector2 mouseDelta = GetMouseDelta();
    if (mouseDelta.x != 0) paddle.x = GetMouseX() - paddle.width / 2;
    if (paddle.x < 0) paddle.x = 0;
    if (paddle.x > W - paddle.width) paddle.x = W - paddle.width;

    if (!launched) {
        ball = (Vector2){paddle.x + paddle.width / 2, paddle.y - 10};
        if (IsKeyPressed(KEY_SPACE) || IsMouseButtonPressed(MOUSE_BUTTON_LEFT)) {
            launched = true;
            ballVel = (Vector2){GetRandomValue(-200, 200), -420};
        }
        return;
    }

    ball.x += ballVel.x * dt;
    ball.y += ballVel.y * dt;
    if (ball.x < 8 || ball.x > W - 8) { ballVel.x = -ballVel.x; ball.x = ball.x < 8 ? 8 : W - 8; }
    if (ball.y < 8) { ballVel.y = -ballVel.y; ball.y = 8; }
    if (ball.y > H + 20) {
        burst((Vector2){ball.x, H - 4}, RED, 60);
        shake = 0.4f;
        if (--lives > 0) reset_ball();
        return;
    }

    // Paddle bounce: the hit position sets the angle.
    if (ballVel.y > 0 && CheckCollisionCircleRec(ball, 8, paddle)) {
        float hit = (ball.x - (paddle.x + paddle.width / 2)) / (paddle.width / 2);
        float speed = sqrtf(ballVel.x * ballVel.x + ballVel.y * ballVel.y) * 1.02f;
        ballVel = (Vector2){hit * speed * 0.8f, -sqrtf(speed * speed * (1 - 0.64f * hit * hit))};
        burst(ball, SKYBLUE, 12);
    }

    for (int r = 0; r < ROWS; r++) {
        for (int c = 0; c < COLS; c++) {
            Brick *b = &bricks[r][c];
            if (!b->alive || !CheckCollisionCircleRec(ball, 8, b->rect)) continue;
            b->alive = false;
            bricksLeft--;
            score += 10 * (ROWS - r);
            shake = 0.15f;
            burst((Vector2){b->rect.x + b->rect.width / 2, b->rect.y + b->rect.height / 2}, b->color, 40);
            // Bounce off the side we hit the most.
            float overlapX = fminf(ball.x + 8 - b->rect.x, b->rect.x + b->rect.width - (ball.x - 8));
            float overlapY = fminf(ball.y + 8 - b->rect.y, b->rect.y + b->rect.height - (ball.y - 8));
            if (overlapX < overlapY) ballVel.x = -ballVel.x; else ballVel.y = -ballVel.y;
            return;
        }
    }
}

static void update_particles(float dt) {
    for (int i = 0; i < MAX_PARTICLES; i++) {
        Particle *p = &particles[i];
        if (p->life <= 0) continue;
        p->vel.y += 500 * dt;
        p->pos.x += p->vel.x * dt;
        p->pos.y += p->vel.y * dt;
        p->life -= dt * 1.4f;
    }
}

int main(void) {
    SetConfigFlags(FLAG_MSAA_4X_HINT | FLAG_VSYNC_HINT);
    InitWindow(W, H, "Breakout - cross-compiled with clang-cl + Conan");
    SetTargetFPS(144);
    reset_game();

    while (!WindowShouldClose()) {
        float dt = GetFrameTime();
        bool over = lives <= 0, won = bricksLeft == 0;
        if (IsKeyPressed(KEY_R) || ((over || won) && IsKeyPressed(KEY_SPACE))) reset_game();
        else if (!over && !won) update(dt);
        update_particles(dt);
        shake = fmaxf(0, shake - dt);

        Camera2D cam = {0};
        cam.zoom = 1;
        if (shake > 0) cam.offset = (Vector2){GetRandomValue(-6, 6) * shake * 3, GetRandomValue(-6, 6) * shake * 3};

        BeginDrawing();
        ClearBackground((Color){12, 12, 24, 255});
        BeginMode2D(cam);
        for (int r = 0; r < ROWS; r++)
            for (int c = 0; c < COLS; c++)
                if (bricks[r][c].alive) DrawRectangleRounded(bricks[r][c].rect, 0.3f, 6, bricks[r][c].color);
        for (int i = 0; i < MAX_PARTICLES; i++)
            if (particles[i].life > 0)
                DrawCircleV(particles[i].pos, 3 * particles[i].life, ColorAlpha(particles[i].color, particles[i].life));
        DrawRectangleRounded(paddle, 0.6f, 8, RAYWHITE);
        DrawCircleV(ball, 8, GOLD);
        EndMode2D();

        DrawText(TextFormat("SCORE %05d", score), 16, 20, 28, RAYWHITE);
        DrawText(TextFormat("LIVES %d", lives), W - 130, 20, 28, RAYWHITE);
        if (!launched && !over && !won) DrawText("SPACE / CLICK TO LAUNCH", W / 2 - 190, H / 2, 28, GRAY);
        if (over) DrawText("GAME OVER - SPACE TO RESTART", W / 2 - 250, H / 2, 32, RED);
        if (won) DrawText("YOU WIN! - SPACE TO PLAY AGAIN", W / 2 - 260, H / 2, 32, GREEN);
        DrawFPS(W / 2 - 40, H - 24);
        EndDrawing();
    }
    CloseWindow();
    return 0;
}
