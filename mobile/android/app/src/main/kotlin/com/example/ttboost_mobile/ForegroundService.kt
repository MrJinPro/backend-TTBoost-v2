package com.mrjinpro.novaboostmobile

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.Service
import android.content.Context
import android.content.Intent
import android.graphics.Color
import android.graphics.drawable.GradientDrawable
import android.graphics.PixelFormat
import android.os.Build
import android.os.IBinder
import android.os.Handler
import android.os.Looper
import android.provider.Settings
import android.util.Log
import android.view.Gravity
import android.view.View
import android.view.WindowManager
import android.widget.Button
import android.widget.ImageButton
import android.widget.LinearLayout
import android.widget.SeekBar
import android.widget.TextView
import androidx.core.app.NotificationCompat

class ForegroundService : Service() {
  companion object {
    const val CHANNEL_ID = "ttboost_foreground"
    const val NOTIFICATION_ID = 7442

    const val ACTION_START = "ttboost.action.START"
    const val ACTION_STOP_SERVICE = "ttboost.action.STOP_SERVICE"
    const val ACTION_STOP_TTS = "ttboost.action.STOP_TTS"
    const val ACTION_STOP_GIFTS = "ttboost.action.STOP_GIFTS"

    const val ACTION_SHOW_OVERLAY = "ttboost.action.SHOW_OVERLAY"
    const val ACTION_HIDE_OVERLAY = "ttboost.action.HIDE_OVERLAY"

    const val ACTION_TTS_VOL_DOWN = "ttboost.action.TTS_VOL_DOWN"
    const val ACTION_TTS_VOL_UP = "ttboost.action.TTS_VOL_UP"
    const val ACTION_GIFTS_VOL_DOWN = "ttboost.action.GIFTS_VOL_DOWN"
    const val ACTION_GIFTS_VOL_UP = "ttboost.action.GIFTS_VOL_UP"

    const val ACTION_TOGGLE_CHAT_SPEAKER = "ttboost.action.TOGGLE_CHAT_SPEAKER"

    const val EXTRA_USERNAME = "tiktokUsername"

    private const val FLUTTER_PREFS = "FlutterSharedPreferences"
    private const val KEY_STOP_TTS = "flutter.overlay_stop_tts"
    private const val KEY_STOP_GIFTS = "flutter.overlay_stop_gifts"

    private const val KEY_WS_CONNECTED = "flutter.overlay_ws_connected"
    private const val KEY_LIVE_CONNECTED = "flutter.overlay_live_connected"
    private const val KEY_TTS_VOL = "flutter.overlay_tts_volume"
    private const val KEY_GIFTS_VOL = "flutter.overlay_gifts_volume"

    private const val KEY_OVERLAY_ALPHA = "flutter.overlay_alpha"
    private const val KEY_OVERLAY_COLLAPSED = "flutter.overlay_collapsed"

    private const val KEY_CMD_TTS_VOL = "flutter.overlay_cmd_tts_volume"
    private const val KEY_CMD_GIFTS_VOL = "flutter.overlay_cmd_gifts_volume"
    private const val KEY_CMD_SET_TTS = "flutter.overlay_cmd_set_tts_volume"
    private const val KEY_CMD_SET_GIFTS = "flutter.overlay_cmd_set_gifts_volume"

    private const val KEY_TEST_TTS = "flutter.overlay_test_tts"

    // Spotify overlay status
    private const val KEY_SPOTIFY_CONNECTED = "flutter.overlay_spotify_connected"
    private const val KEY_SPOTIFY_IS_PLAYING = "flutter.overlay_spotify_is_playing"
    private const val KEY_SPOTIFY_TRACK = "flutter.overlay_spotify_track"
    private const val KEY_SPOTIFY_ARTIST = "flutter.overlay_spotify_artist"
    private const val KEY_SPOTIFY_VOLUME = "flutter.overlay_spotify_volume"

    // Spotify overlay commands (written by native overlay, consumed by Flutter)
    private const val KEY_CMD_SPOTIFY_PLAY_PAUSE = "flutter.overlay_spotify_cmd_play_pause"
    private const val KEY_CMD_SPOTIFY_NEXT = "flutter.overlay_spotify_cmd_next"
    private const val KEY_CMD_SPOTIFY_PREV = "flutter.overlay_spotify_cmd_prev"
    private const val KEY_CMD_SPOTIFY_VOL = "flutter.overlay_spotify_cmd_volume"
    private const val KEY_CMD_SET_SPOTIFY_VOL = "flutter.overlay_spotify_cmd_set_volume"

    // Audio output settings (Flutter SharedPreferences keys).
    private const val KEY_AUDIO_PRIORITY_SPEAKER_WHEN_LIVE = "flutter.audio_output_priority_speaker_when_live"

    private const val KEY_FGS_LAST_ERROR = "flutter.fgs_last_error"

    fun start(context: Context, tiktokUsername: String?) {
      val i = Intent(context, ForegroundService::class.java).apply {
        action = ACTION_START
        if (tiktokUsername != null) putExtra(EXTRA_USERNAME, tiktokUsername)
      }
      // Foreground Service / persistent notification intentionally removed.
      // Keep service as a regular (best-effort) service to manage overlay only.
      context.startService(i)
    }

    fun stop(context: Context) {
      val i = Intent(context, ForegroundService::class.java).apply {
        action = ACTION_STOP_SERVICE
      }
      context.startService(i)
    }

    fun showOverlay(context: Context) {
      val i = Intent(context, ForegroundService::class.java).apply {
        action = ACTION_SHOW_OVERLAY
      }
      // Do NOT use startForegroundService() because we don't call startForeground().
      context.startService(i)
    }

    fun hideOverlay(context: Context) {
      val i = Intent(context, ForegroundService::class.java).apply {
        action = ACTION_HIDE_OVERLAY
      }
      context.startService(i)
    }
  }

  override fun onBind(intent: Intent?): IBinder? = null

  override fun onCreate() {
    super.onCreate()
    // Defensive: if older builds left a sticky notification, clear it.
    try {
      val nm = getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
      nm.cancel(NOTIFICATION_ID)
    } catch (_: Throwable) {
    }
  }

  private val handler = Handler(Looper.getMainLooper())
  private var lastUsername: String? = null

  private var wm: WindowManager? = null
  private var overlayView: View? = null
  private var overlayStatusText: TextView? = null
  private var overlayUserText: TextView? = null
  private var overlayIndicator: View? = null
  private var overlayBody: View? = null
  private var overlayOpacitySeek: SeekBar? = null
  private var overlayTtsSeek: SeekBar? = null
  private var overlayGiftsSeek: SeekBar? = null
  private var overlayTtsValueText: TextView? = null
  private var overlayGiftsValueText: TextView? = null
  private var overlayChatSpeakerBtn: Button? = null
  private var overlaySpotifyInfoText: TextView? = null
  private var overlaySpotifyPlayBtn: Button? = null
  private var overlaySpotifyVolSeek: SeekBar? = null
  private var overlaySpotifyVolValueText: TextView? = null
  private var overlayCloseBtn: ImageButton? = null
  private var overlayCollapsed: Boolean = false
  private var overlayAlpha: Float = 0.85f
  private var overlayParams: WindowManager.LayoutParams? = null

  private fun dp(value: Int): Int = (value * resources.displayMetrics.density).toInt()

  private val ticker = object : Runnable {
    override fun run() {
      try {
        updateOverlayUi()
      } catch (_: Throwable) {
      }
      handler.postDelayed(this, 1000)
    }
  }

  override fun onDestroy() {
    try {
      handler.removeCallbacks(ticker)
    } catch (_: Throwable) {
    }
    try {
      removeOverlay()
    } catch (_: Throwable) {
    }
    super.onDestroy()
  }

  override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
    when (intent?.action) {
      ACTION_START -> {
        val username = intent.getStringExtra(EXTRA_USERNAME)
        lastUsername = username
        writeFlutterString(KEY_FGS_LAST_ERROR, "")
        try {
          ensureOverlay()
        } catch (_: Throwable) {
        }
        try {
          handler.removeCallbacks(ticker)
          handler.postDelayed(ticker, 800)
        } catch (_: Throwable) {
        }
      }

      ACTION_SHOW_OVERLAY -> {
        try {
          ensureOverlay()
        } catch (t: Throwable) {
          val msg = "Overlay show failed: ${t.javaClass.simpleName}: ${t.message}"
          Log.e("NovaBoostOverlay", msg, t)
          writeFlutterString(KEY_FGS_LAST_ERROR, msg)
        }
        try {
          handler.removeCallbacks(ticker)
          handler.postDelayed(ticker, 800)
        } catch (_: Throwable) {
        }
      }

      ACTION_HIDE_OVERLAY -> {
        try {
          removeOverlay()
        } catch (_: Throwable) {
        }
        try {
          handler.removeCallbacks(ticker)
        } catch (_: Throwable) {
        }
        // Stop service when overlay is hidden.
        stopSelf()
        return START_NOT_STICKY
      }

      ACTION_STOP_TTS -> {
        setFlutterBool(KEY_STOP_TTS, true)
        // keep running
      }
      ACTION_STOP_GIFTS -> {
        setFlutterBool(KEY_STOP_GIFTS, true)
      }
      ACTION_TTS_VOL_DOWN -> {
        nudgeVolume(isTts = true, delta = -10)
      }
      ACTION_TTS_VOL_UP -> {
        nudgeVolume(isTts = true, delta = 10)
      }
      ACTION_GIFTS_VOL_DOWN -> {
        nudgeVolume(isTts = false, delta = -10)
      }
      ACTION_GIFTS_VOL_UP -> {
        nudgeVolume(isTts = false, delta = 10)
      }

      ACTION_TOGGLE_CHAT_SPEAKER -> {
        val current = readFlutterBool(KEY_AUDIO_PRIORITY_SPEAKER_WHEN_LIVE, false)
        setFlutterBool(KEY_AUDIO_PRIORITY_SPEAKER_WHEN_LIVE, !current)
        updateOverlayUi()
      }
      ACTION_STOP_SERVICE -> {
        try {
          handler.removeCallbacks(ticker)
        } catch (_: Throwable) {
        }
        try {
          removeOverlay()
        } catch (_: Throwable) {
        }
        try {
          val nm = getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
          nm.cancel(NOTIFICATION_ID)
        } catch (_: Throwable) {
        }
        stopForeground(STOP_FOREGROUND_REMOVE)
        stopSelf()
        return START_NOT_STICKY
      }
      else -> {
        // no-op
      }
    }

    return START_STICKY
  }

  private fun canDrawOverlays(): Boolean {
    return try {
      if (Build.VERSION.SDK_INT < Build.VERSION_CODES.M) true else Settings.canDrawOverlays(this)
    } catch (_: Throwable) {
      false
    }
  }

  private fun ensureOverlay() {
    if (overlayView != null) return
    if (!canDrawOverlays()) {
      writeFlutterString(KEY_FGS_LAST_ERROR, "Overlay permission missing (SYSTEM_ALERT_WINDOW)")
      return
    }

    // Restore persisted overlay UI prefs.
    overlayCollapsed = readFlutterBool(KEY_OVERLAY_COLLAPSED, false)
    overlayAlpha = readFlutterDouble(KEY_OVERLAY_ALPHA, 0.85).toFloat().coerceIn(0.2f, 1.0f)

    val windowManager = getSystemService(WINDOW_SERVICE) as WindowManager
    wm = windowManager

    val type = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
      WindowManager.LayoutParams.TYPE_APPLICATION_OVERLAY
    } else {
      @Suppress("DEPRECATION")
      WindowManager.LayoutParams.TYPE_PHONE
    }

    val params = WindowManager.LayoutParams(
      WindowManager.LayoutParams.WRAP_CONTENT,
      WindowManager.LayoutParams.WRAP_CONTENT,
      type,
      WindowManager.LayoutParams.FLAG_NOT_FOCUSABLE or
        WindowManager.LayoutParams.FLAG_LAYOUT_IN_SCREEN,
      PixelFormat.TRANSLUCENT
    ).apply {
      gravity = Gravity.TOP or Gravity.END
      x = 0
      y = 140
    }
    overlayParams = params

    val root = LinearLayout(this).apply {
      orientation = LinearLayout.VERTICAL
      setPadding(0, 0, 0, 0)

      val bg = GradientDrawable().apply {
        shape = GradientDrawable.RECTANGLE
        cornerRadius = dp(18).toFloat()
        setColor(Color.argb(235, 18, 18, 18))
        setStroke(dp(1), Color.argb(90, 255, 255, 255))
      }
      background = bg
      alpha = overlayAlpha
    }

    val header = LinearLayout(this).apply {
      orientation = LinearLayout.HORIZONTAL
      gravity = Gravity.CENTER_VERTICAL
      setPadding(dp(12), dp(10), dp(8), dp(10))
    }

    val handle = LinearLayout(this).apply {
      orientation = LinearLayout.HORIZONTAL
      gravity = Gravity.CENTER_VERTICAL
      layoutParams = LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.WRAP_CONTENT, 1f)
    }

    val indicator = View(this).apply {
      val d = GradientDrawable().apply {
        shape = GradientDrawable.OVAL
        setColor(Color.RED)
      }
      background = d
      val size = dp(10)
      layoutParams = LinearLayout.LayoutParams(size, size).apply {
        rightMargin = dp(10)
      }
    }
    overlayIndicator = indicator
    handle.addView(indicator)

    val user = TextView(this).apply {
      text = ""
      setTextColor(Color.WHITE)
      textSize = 14f
      maxLines = 1
      setPadding(0, 0, dp(10), 0)
      layoutParams = LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.WRAP_CONTENT, 1f)
    }
    overlayUserText = user
    handle.addView(user)

    header.addView(handle)

    val closeBtn = ImageButton(this).apply {
      setImageResource(android.R.drawable.ic_menu_close_clear_cancel)
      setBackgroundColor(Color.TRANSPARENT)
      setColorFilter(Color.LTGRAY)
      setPadding(dp(6), dp(6), dp(6), dp(6))
      setOnClickListener { removeOverlay() }
    }
    overlayCloseBtn = closeBtn
    header.addView(closeBtn)

    root.addView(header)

    val body = LinearLayout(this).apply {
      orientation = LinearLayout.VERTICAL
      setPadding(dp(12), 0, dp(12), dp(12))
    }
    overlayBody = body

    val status = TextView(this).apply {
      text = "overlay: init"
      setTextColor(Color.LTGRAY)
      textSize = 12f
      setPadding(0, dp(2), 0, dp(10))
    }
    overlayStatusText = status
    body.addView(status)

    fun smallButton(label: String, onClick: () -> Unit): Button {
      return Button(this).apply {
        text = label
        isAllCaps = false
        textSize = 12f
        setOnClickListener { onClick() }
        setPadding(dp(10), dp(8), dp(10), dp(8))
        minHeight = dp(34)
        minimumHeight = dp(34)
      }
    }

    val row1 = LinearLayout(this).apply {
      orientation = LinearLayout.HORIZONTAL
    }
    val btnStopTts = smallButton("Stop TTS") { setFlutterBool(KEY_STOP_TTS, true) }
    val btnTestTts = smallButton("Test TTS") { setFlutterBool(KEY_TEST_TTS, true) }
    row1.addView(btnStopTts, LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.WRAP_CONTENT, 1f).apply { rightMargin = dp(8) })
    row1.addView(btnTestTts, LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.WRAP_CONTENT, 1f))
    body.addView(row1)

    val row1b = LinearLayout(this).apply {
      orientation = LinearLayout.HORIZONTAL
      setPadding(0, dp(8), 0, 0)
    }
    val btnStopGifts = smallButton("Stop Gifts") { setFlutterBool(KEY_STOP_GIFTS, true) }
    row1b.addView(btnStopGifts, LinearLayout.LayoutParams(LinearLayout.LayoutParams.MATCH_PARENT, LinearLayout.LayoutParams.WRAP_CONTENT))
    body.addView(row1b)

    val rowSpeaker = LinearLayout(this).apply {
      orientation = LinearLayout.HORIZONTAL
      setPadding(0, dp(8), 0, 0)
    }
    val btnChatSpeaker = smallButton("Чат → динамик: ...") {
      val current = readFlutterBool(KEY_AUDIO_PRIORITY_SPEAKER_WHEN_LIVE, false)
      setFlutterBool(KEY_AUDIO_PRIORITY_SPEAKER_WHEN_LIVE, !current)
      updateOverlayUi()
      updateNotification(lastUsername)
    }
    overlayChatSpeakerBtn = btnChatSpeaker
    rowSpeaker.addView(btnChatSpeaker, LinearLayout.LayoutParams(LinearLayout.LayoutParams.MATCH_PARENT, LinearLayout.LayoutParams.WRAP_CONTENT))
    body.addView(rowSpeaker)

    // Spotify mini-player (controls + separate Spotify volume)
    val spotifyHeader = TextView(this).apply {
      text = "Spotify"
      setTextColor(Color.WHITE)
      textSize = 13f
      setPadding(0, dp(12), 0, dp(4))
    }
    body.addView(spotifyHeader)

    val spotifyInfo = TextView(this).apply {
      text = "Spotify: не подключено"
      setTextColor(Color.LTGRAY)
      textSize = 12f
    }
    overlaySpotifyInfoText = spotifyInfo
    body.addView(spotifyInfo)

    val spotifyRow = LinearLayout(this).apply {
      orientation = LinearLayout.HORIZONTAL
      setPadding(0, dp(8), 0, 0)
    }

    val btnPrev = smallButton("Prev") {
      setFlutterBool(KEY_CMD_SPOTIFY_PREV, true)
    }
    val btnPlay = smallButton("Play") {
      setFlutterBool(KEY_CMD_SPOTIFY_PLAY_PAUSE, true)
    }
    val btnNext = smallButton("Next") {
      setFlutterBool(KEY_CMD_SPOTIFY_NEXT, true)
    }
    overlaySpotifyPlayBtn = btnPlay

    spotifyRow.addView(btnPrev, LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.WRAP_CONTENT, 1f).apply { rightMargin = dp(8) })
    spotifyRow.addView(btnPlay, LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.WRAP_CONTENT, 1f).apply { rightMargin = dp(8) })
    spotifyRow.addView(btnNext, LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.WRAP_CONTENT, 1f))
    body.addView(spotifyRow)

    fun volumeRow(label: String, initial: Int): Pair<LinearLayout, Triple<SeekBar, TextView, TextView>> {
      val wrap = LinearLayout(this).apply {
        orientation = LinearLayout.VERTICAL
        setPadding(0, dp(10), 0, 0)
      }

      val titleRow = LinearLayout(this).apply {
        orientation = LinearLayout.HORIZONTAL
        gravity = Gravity.CENTER_VERTICAL
      }

      val title = TextView(this).apply {
        text = label
        setTextColor(Color.LTGRAY)
        textSize = 12f
        layoutParams = LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.WRAP_CONTENT, 1f)
      }
      val valueTv = TextView(this).apply {
        text = "$initial%"
        setTextColor(Color.WHITE)
        textSize = 12f
      }
      titleRow.addView(title)
      titleRow.addView(valueTv)
      wrap.addView(titleRow)

      val seek = SeekBar(this).apply {
        max = 100
        progress = initial.coerceIn(0, 100)
      }
      wrap.addView(seek)
      return Pair(wrap, Triple(seek, title, valueTv))
    }

    val initialTts = readFlutterDouble(KEY_TTS_VOL, 100.0).toInt().coerceIn(0, 100)
    val (ttsWrap, ttsParts) = volumeRow("TTS громкость", initialTts)
    val ttsSeek = ttsParts.first
    val ttsValueTv = ttsParts.third
    overlayTtsSeek = ttsSeek
    overlayTtsValueText = ttsValueTv
    ttsSeek.setOnSeekBarChangeListener(object : SeekBar.OnSeekBarChangeListener {
      override fun onProgressChanged(seekBar: SeekBar?, progress: Int, fromUser: Boolean) {
        if (!fromUser) return
        val p = progress.coerceIn(0, 100)
        ttsValueTv.text = "$p%"
      }

      override fun onStartTrackingTouch(seekBar: SeekBar?) {}
      override fun onStopTrackingTouch(seekBar: SeekBar?) {
        val p = (seekBar?.progress ?: initialTts).coerceIn(0, 100)
        // Optimistic UI: immediately reflect new value in overlay while Flutter applies it.
        writeFlutterDouble(KEY_TTS_VOL, p.toDouble())
        writeFlutterDouble(KEY_CMD_TTS_VOL, p.toDouble())
        setFlutterBool(KEY_CMD_SET_TTS, true)
        updateNotification(lastUsername)
      }
    })
    body.addView(ttsWrap)

    val initialGifts = readFlutterDouble(KEY_GIFTS_VOL, 100.0).toInt().coerceIn(0, 100)
    val (giftsWrap, giftsParts) = volumeRow("GIFTS громкость", initialGifts)
    val giftsSeek = giftsParts.first
    val giftsValueTv = giftsParts.third
    overlayGiftsSeek = giftsSeek
    overlayGiftsValueText = giftsValueTv
    giftsSeek.setOnSeekBarChangeListener(object : SeekBar.OnSeekBarChangeListener {
      override fun onProgressChanged(seekBar: SeekBar?, progress: Int, fromUser: Boolean) {
        if (!fromUser) return
        val p = progress.coerceIn(0, 100)
        giftsValueTv.text = "$p%"
      }

      override fun onStartTrackingTouch(seekBar: SeekBar?) {}
      override fun onStopTrackingTouch(seekBar: SeekBar?) {
        val p = (seekBar?.progress ?: initialGifts).coerceIn(0, 100)
        // Optimistic UI: immediately reflect new value in overlay while Flutter applies it.
        writeFlutterDouble(KEY_GIFTS_VOL, p.toDouble())
        writeFlutterDouble(KEY_CMD_GIFTS_VOL, p.toDouble())
        setFlutterBool(KEY_CMD_SET_GIFTS, true)
        updateNotification(lastUsername)
      }
    })
    body.addView(giftsWrap)

    val initialSpotifyVol = readFlutterDouble(KEY_SPOTIFY_VOLUME, 0.0).toInt().coerceIn(0, 100)
    val (spotifyWrap, spotifyParts) = volumeRow("Spotify громкость", initialSpotifyVol)
    val spotifySeek = spotifyParts.first
    val spotifyValueTv = spotifyParts.third
    overlaySpotifyVolSeek = spotifySeek
    overlaySpotifyVolValueText = spotifyValueTv
    spotifySeek.setOnSeekBarChangeListener(object : SeekBar.OnSeekBarChangeListener {
      override fun onProgressChanged(seekBar: SeekBar?, progress: Int, fromUser: Boolean) {
        if (!fromUser) return
        val p = progress.coerceIn(0, 100)
        spotifyValueTv.text = "$p%"
      }

      override fun onStartTrackingTouch(seekBar: SeekBar?) {}
      override fun onStopTrackingTouch(seekBar: SeekBar?) {
        val p = (seekBar?.progress ?: initialSpotifyVol).coerceIn(0, 100)
        writeFlutterDouble(KEY_SPOTIFY_VOLUME, p.toDouble())
        writeFlutterDouble(KEY_CMD_SPOTIFY_VOL, p.toDouble())
        setFlutterBool(KEY_CMD_SET_SPOTIFY_VOL, true)
        updateNotification(lastUsername)
      }
    })
    body.addView(spotifyWrap)

    val opacityRow = LinearLayout(this).apply {
      orientation = LinearLayout.VERTICAL
      setPadding(0, dp(10), 0, 0)
    }
    val opacityLabel = TextView(this).apply {
      text = "Прозрачность"
      setTextColor(Color.LTGRAY)
      textSize = 12f
      setPadding(0, 0, 0, dp(4))
    }
    opacityRow.addView(opacityLabel)
    val opacitySeek = SeekBar(this).apply {
      max = 100
      val initial = (overlayAlpha * 100f).toInt().coerceIn(20, 100)
      progress = initial
      setOnSeekBarChangeListener(object : SeekBar.OnSeekBarChangeListener {
        override fun onProgressChanged(seekBar: SeekBar?, progress: Int, fromUser: Boolean) {
          val p = progress.coerceIn(20, 100)
          overlayAlpha = (p / 100f)
          root.alpha = overlayAlpha
          writeFlutterDouble(KEY_OVERLAY_ALPHA, overlayAlpha.toDouble())
        }

        override fun onStartTrackingTouch(seekBar: SeekBar?) {}
        override fun onStopTrackingTouch(seekBar: SeekBar?) {}
      })
    }
    overlayOpacitySeek = opacitySeek
    opacityRow.addView(opacitySeek)
    body.addView(opacityRow)

    root.addView(body)

    fun applyCollapsedState(collapsed: Boolean) {
      overlayCollapsed = collapsed
      body.visibility = if (collapsed) View.GONE else View.VISIBLE
      closeBtn.visibility = if (collapsed) View.GONE else View.VISIBLE
      setFlutterBool(KEY_OVERLAY_COLLAPSED, collapsed)
      updateOverlayUi()
    }

    // Tap on handle toggles collapsed state; drag on handle moves overlay.
    handle.setOnTouchListener(object : View.OnTouchListener {
      private var lastX = 0
      private var lastY = 0
      private var startTouchX = 0f
      private var startTouchY = 0f
      private var moved = false
      private val slop = dp(6)

      override fun onTouch(v: View, event: android.view.MotionEvent): Boolean {
        val p = overlayParams ?: return false
        when (event.action) {
          android.view.MotionEvent.ACTION_DOWN -> {
            lastX = p.x
            lastY = p.y
            startTouchX = event.rawX
            startTouchY = event.rawY
            moved = false
            return true
          }
          android.view.MotionEvent.ACTION_MOVE -> {
            val dxF = (startTouchX - event.rawX)
            val dyF = (event.rawY - startTouchY)
            if (!moved && (kotlin.math.abs(dxF) + kotlin.math.abs(dyF)) > slop) {
              moved = true
            }
            if (moved) {
              val dx = dxF.toInt()
              val dy = dyF.toInt()
              p.x = (lastX + dx).coerceAtLeast(0)
              p.y = (lastY + dy).coerceAtLeast(0)
              try {
                wm?.updateViewLayout(overlayView, p)
              } catch (_: Throwable) {
              }
            }
            return true
          }
          android.view.MotionEvent.ACTION_UP -> {
            if (!moved) {
              applyCollapsedState(!overlayCollapsed)
            }
            return true
          }
        }
        return false
      }
    })

    overlayView = root
    windowManager.addView(root, params)
    // Apply collapsed state after view is attached.
    try {
      (overlayBody)?.visibility = if (overlayCollapsed) View.GONE else View.VISIBLE
      (overlayCloseBtn)?.visibility = if (overlayCollapsed) View.GONE else View.VISIBLE
    } catch (_: Throwable) {
    }
    updateOverlayUi()
  }

  private fun removeOverlay() {
    val view = overlayView ?: return
    try {
      wm?.removeView(view)
    } catch (_: Throwable) {
    }
    overlayView = null
    overlayStatusText = null
    overlayUserText = null
    overlayIndicator = null
    overlayBody = null
    overlayOpacitySeek = null
    overlayTtsSeek = null
    overlayGiftsSeek = null
    overlayTtsValueText = null
    overlayGiftsValueText = null
    overlayChatSpeakerBtn = null
    overlaySpotifyInfoText = null
    overlaySpotifyPlayBtn = null
    overlaySpotifyVolSeek = null
    overlaySpotifyVolValueText = null
    overlayCloseBtn = null
    overlayParams = null
  }

  private fun updateOverlayUi() {
    val view = overlayView ?: return
    val statusTv = overlayStatusText
    val wsOk = readFlutterBool(KEY_WS_CONNECTED, false)
    val liveOk = readFlutterBool(KEY_LIVE_CONNECTED, false)

    val connected = wsOk && liveOk
    try {
      val bg = overlayIndicator?.background
      if (bg is GradientDrawable) {
        bg.setColor(if (connected) Color.rgb(0, 200, 90) else Color.rgb(220, 50, 50))
      }
    } catch (_: Throwable) {
    }

    val statusText = if (wsOk) {
      if (liveOk) "LIVE: подключено" else "LIVE: не подключено"
    } else {
      "WS: нет соединения"
    }
    try {
      statusTv?.text = statusText
    } catch (_: Throwable) {
    }

    val u = lastUsername ?: ""
    overlayUserText?.text = if (u.isNotEmpty()) "@$u" else "NovaBoost"

    try {
      val ttsVol = readFlutterDouble(KEY_TTS_VOL, 100.0).toInt().coerceIn(0, 100)
      val giftsVol = readFlutterDouble(KEY_GIFTS_VOL, 100.0).toInt().coerceIn(0, 100)

      // Keep sliders in sync with app state when not actively dragged.
      overlayTtsValueText?.text = "$ttsVol%"
      overlayGiftsValueText?.text = "$giftsVol%"
      overlayTtsSeek?.let { if (!it.isPressed && it.progress != ttsVol) it.progress = ttsVol }
      overlayGiftsSeek?.let { if (!it.isPressed && it.progress != giftsVol) it.progress = giftsVol }
    } catch (_: Throwable) {
    }

    // Spotify mini-player status
    try {
      val spConnected = readFlutterBool(KEY_SPOTIFY_CONNECTED, false)
      val spPlaying = readFlutterBool(KEY_SPOTIFY_IS_PLAYING, false)
      val spTrack = readFlutterString(KEY_SPOTIFY_TRACK, "").trim()
      val spArtist = readFlutterString(KEY_SPOTIFY_ARTIST, "").trim()
      val spVol = readFlutterDouble(KEY_SPOTIFY_VOLUME, 0.0).toInt().coerceIn(0, 100)

      overlaySpotifyPlayBtn?.text = if (spPlaying) "Pause" else "Play"
      overlaySpotifyVolValueText?.text = "$spVol%"
      overlaySpotifyVolSeek?.let { if (!it.isPressed && it.progress != spVol) it.progress = spVol }

      val info = if (!spConnected) {
        "Spotify: не подключено"
      } else {
        val title = if (spTrack.isNotEmpty()) spTrack else "—"
        val by = if (spArtist.isNotEmpty()) " — $spArtist" else ""
        "Spotify: $title$by"
      }
      overlaySpotifyInfoText?.text = info
    } catch (_: Throwable) {
    }

    try {
      val on = readFlutterBool(KEY_AUDIO_PRIORITY_SPEAKER_WHEN_LIVE, false)
      overlayChatSpeakerBtn?.text = if (on) "Чат → динамик: ВКЛ" else "Чат → динамик: ВЫКЛ"
    } catch (_: Throwable) {
    }
    // When collapsed, keep only indicator + nickname visible.
    try {
      overlayBody?.visibility = if (overlayCollapsed) View.GONE else View.VISIBLE
      overlayCloseBtn?.visibility = if (overlayCollapsed) View.GONE else View.VISIBLE
    } catch (_: Throwable) {
    }
    // keep reference used
    view.invalidate()
  }

  private fun setFlutterBool(key: String, value: Boolean) {
    try {
      val prefs = getSharedPreferences(FLUTTER_PREFS, Context.MODE_PRIVATE)
      prefs.edit().putBoolean(key, value).apply()
    } catch (_: Throwable) {
    }
  }

  private fun writeFlutterString(key: String, value: String) {
    try {
      val prefs = getSharedPreferences(FLUTTER_PREFS, Context.MODE_PRIVATE)
      prefs.edit().putString(key, value).apply()
    } catch (_: Throwable) {
    }
  }

  private fun readFlutterString(key: String, def: String = ""): String {
    return try {
      val prefs = getSharedPreferences(FLUTTER_PREFS, Context.MODE_PRIVATE)
      prefs.getString(key, def) ?: def
    } catch (_: Throwable) {
      def
    }
  }

  private fun readFlutterBool(key: String, def: Boolean = false): Boolean {
    return try {
      val prefs = getSharedPreferences(FLUTTER_PREFS, Context.MODE_PRIVATE)
      prefs.getBoolean(key, def)
    } catch (_: Throwable) {
      def
    }
  }

  private fun readFlutterDouble(key: String, def: Double): Double {
    return try {
      val prefs = getSharedPreferences(FLUTTER_PREFS, Context.MODE_PRIVATE)
      // SharedPreferences in Android has no double; Flutter stores doubles as "Double" internally,
      // but on Android it is saved as float/long depending on plugin version.
      // We safely try multiple types.
      val all = prefs.all
      val v = all[key]
      when (v) {
        is Float -> v.toDouble()
        is Double -> v
        is Int -> v.toDouble()
        is Long -> java.lang.Double.longBitsToDouble(v)
        is String -> v.toDoubleOrNull() ?: def
        else -> def
      }
    } catch (_: Throwable) {
      def
    }
  }

  private fun writeFlutterDouble(key: String, value: Double) {
    try {
      val prefs = getSharedPreferences(FLUTTER_PREFS, Context.MODE_PRIVATE)
      // Store as string to avoid float/long ambiguity across plugin versions.
      prefs.edit().putString(key, value.toString()).apply()
    } catch (_: Throwable) {
    }
  }

  private fun nudgeVolume(isTts: Boolean, delta: Int) {
    val current = if (isTts) readFlutterDouble(KEY_TTS_VOL, 100.0) else readFlutterDouble(KEY_GIFTS_VOL, 100.0)
    var next = current + delta
    if (next < 0) next = 0.0
    if (next > 100) next = 100.0

    if (isTts) {
      writeFlutterDouble(KEY_CMD_TTS_VOL, next)
      setFlutterBool(KEY_CMD_SET_TTS, true)
    } else {
      writeFlutterDouble(KEY_CMD_GIFTS_VOL, next)
      setFlutterBool(KEY_CMD_SET_GIFTS, true)
    }
  }

  private fun startForegroundInternal(username: String?) {
    // Foreground Service / persistent notification intentionally disabled.
    // Keep method for backward-compat, but never show a notification.
    cancelNotification()
  }

  private fun updateNotification(username: String?) {
    // Notifications intentionally disabled.
    cancelNotification()
  }

  private fun cancelNotification() {
    try {
      val nm = getSystemService(NOTIFICATION_SERVICE) as NotificationManager
      nm.cancel(NOTIFICATION_ID)
    } catch (_: Throwable) {
    }
  }

  private fun createChannel() {
    if (Build.VERSION.SDK_INT < Build.VERSION_CODES.O) return
    val nm = getSystemService(NOTIFICATION_SERVICE) as NotificationManager
    val ch = NotificationChannel(
      CHANNEL_ID,
      "NovaBoost background",
      NotificationManager.IMPORTANCE_LOW
    ).apply {
      description = "Keeps NovaBoost running in background"
      setShowBadge(false)
    }
    nm.createNotificationChannel(ch)
  }

  private fun buildNotification(username: String?): Notification {
    val title = "NovaBoost Mobile"
    val wsOk = readFlutterBool(KEY_WS_CONNECTED, false)
    val liveOk = readFlutterBool(KEY_LIVE_CONNECTED, false)
    val ttsVol = readFlutterDouble(KEY_TTS_VOL, 100.0).toInt().coerceIn(0, 100)
    val giftsVol = readFlutterDouble(KEY_GIFTS_VOL, 100.0).toInt().coerceIn(0, 100)

    val namePart = if (!username.isNullOrBlank()) "@$username" else ""
    val content = "${if (wsOk) "WS✓" else "WS✗"} ${if (liveOk) "LIVE✓" else "LIVE✗"}  TTS $ttsVol  Gifts $giftsVol ${namePart}".trim()

    val stopTtsIntent = Intent(this, ForegroundService::class.java).apply {
      action = ACTION_STOP_TTS
      if (username != null) putExtra(EXTRA_USERNAME, username)
    }
    val stopGiftsIntent = Intent(this, ForegroundService::class.java).apply {
      action = ACTION_STOP_GIFTS
      if (username != null) putExtra(EXTRA_USERNAME, username)
    }
    val stopServiceIntent = Intent(this, ForegroundService::class.java).apply {
      action = ACTION_STOP_SERVICE
    }

    val ttsDownIntent = Intent(this, ForegroundService::class.java).apply {
      action = ACTION_TTS_VOL_DOWN
    }
    val ttsUpIntent = Intent(this, ForegroundService::class.java).apply {
      action = ACTION_TTS_VOL_UP
    }
    val giftsDownIntent = Intent(this, ForegroundService::class.java).apply {
      action = ACTION_GIFTS_VOL_DOWN
    }
    val giftsUpIntent = Intent(this, ForegroundService::class.java).apply {
      action = ACTION_GIFTS_VOL_UP
    }

    val toggleChatSpeakerIntent = Intent(this, ForegroundService::class.java).apply {
      action = ACTION_TOGGLE_CHAT_SPEAKER
    }

    val flags = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M) {
      android.app.PendingIntent.FLAG_UPDATE_CURRENT or android.app.PendingIntent.FLAG_IMMUTABLE
    } else {
      android.app.PendingIntent.FLAG_UPDATE_CURRENT
    }

    val pStopTts = android.app.PendingIntent.getService(this, 1, stopTtsIntent, flags)
    val pStopGifts = android.app.PendingIntent.getService(this, 2, stopGiftsIntent, flags)
    val pStopService = android.app.PendingIntent.getService(this, 3, stopServiceIntent, flags)

    val pTtsDown = android.app.PendingIntent.getService(this, 4, ttsDownIntent, flags)
    val pTtsUp = android.app.PendingIntent.getService(this, 5, ttsUpIntent, flags)
    val pGiftsDown = android.app.PendingIntent.getService(this, 6, giftsDownIntent, flags)
    val pGiftsUp = android.app.PendingIntent.getService(this, 7, giftsUpIntent, flags)

    val pToggleChatSpeaker = android.app.PendingIntent.getService(this, 8, toggleChatSpeakerIntent, flags)

    val chatSpeakerOn = readFlutterBool(KEY_AUDIO_PRIORITY_SPEAKER_WHEN_LIVE, false)
    val chatSpeakerLabel = if (chatSpeakerOn) "Chat→SPK:ON" else "Chat→SPK:OFF"

    return NotificationCompat.Builder(this, CHANNEL_ID)
      .setContentTitle(title)
      .setContentText(content)
      .setSmallIcon(android.R.drawable.ic_media_play)
      .setOngoing(true)
      .setOnlyAlertOnce(true)
      .setCategory(NotificationCompat.CATEGORY_SERVICE)
      .setPriority(NotificationCompat.PRIORITY_LOW)
      .addAction(android.R.drawable.ic_media_previous, "TTS-", pTtsDown)
      .addAction(android.R.drawable.ic_media_next, "TTS+", pTtsUp)
      .addAction(android.R.drawable.ic_media_previous, "G-", pGiftsDown)
      .addAction(android.R.drawable.ic_media_next, "G+", pGiftsUp)
      .addAction(android.R.drawable.ic_media_pause, "Stop TTS", pStopTts)
      .addAction(android.R.drawable.ic_media_pause, "Stop Gifts", pStopGifts)
      .addAction(android.R.drawable.ic_lock_silent_mode_off, chatSpeakerLabel, pToggleChatSpeaker)
      .addAction(android.R.drawable.ic_menu_close_clear_cancel, "Stop", pStopService)
      .build()
  }
}
