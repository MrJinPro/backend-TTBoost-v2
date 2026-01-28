package com.mrjinpro.novaboostmobile

import android.content.Context
import android.media.AudioAttributes
import android.media.AudioDeviceInfo
import android.media.AudioManager
import android.media.MediaPlayer
import android.os.Build
import io.flutter.embedding.engine.FlutterEngine
import io.flutter.embedding.android.FlutterActivity
import io.flutter.plugin.common.MethodChannel

class MainActivity : FlutterActivity() {
	private val channelName = "ttboost/foreground_service"

	private data class AudioRouteState(
		val mode: Int,
		val speakerOn: Boolean,
		val scoOn: Boolean,
	)

	private val audioRouteTokens = HashMap<Int, AudioRouteState>()
	private var nextAudioRouteToken: Int = 1

	private var speakerPlayer: MediaPlayer? = null
	private var speakerToken: Int? = null

	private fun audioManager(): AudioManager {
		return getSystemService(Context.AUDIO_SERVICE) as AudioManager
	}

	private fun beginSpeakerRoute(): Int {
		val am = audioManager()
		val token = nextAudioRouteToken++
		audioRouteTokens[token] = AudioRouteState(
			mode = am.mode,
			speakerOn = am.isSpeakerphoneOn,
			scoOn = am.isBluetoothScoOn,
		)
		try {
			// Best-effort: try to keep BT SCO from hijacking, then enable speaker.
			try { am.stopBluetoothSco() } catch (_: Throwable) {}
			try { am.isBluetoothScoOn = false } catch (_: Throwable) {}
			try { am.mode = AudioManager.MODE_IN_COMMUNICATION } catch (_: Throwable) {}
			try { am.isSpeakerphoneOn = true } catch (_: Throwable) {}

			if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
				try {
					val speaker = am.availableCommunicationDevices.firstOrNull { d ->
						d.type == AudioDeviceInfo.TYPE_BUILTIN_SPEAKER
					}
					if (speaker != null) {
						am.setCommunicationDevice(speaker)
					}
				} catch (_: Throwable) {}
			}
		} catch (_: Throwable) {}
		return token
	}

	private fun endSpeakerRoute(token: Int) {
		val state = audioRouteTokens.remove(token) ?: return
		val am = audioManager()
		try {
			if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
				try { am.clearCommunicationDevice() } catch (_: Throwable) {}
			}
			try { am.isSpeakerphoneOn = state.speakerOn } catch (_: Throwable) {}
			try {
				if (state.scoOn) {
					am.startBluetoothSco()
					am.isBluetoothScoOn = true
				} else {
					am.stopBluetoothSco()
					am.isBluetoothScoOn = false
				}
			} catch (_: Throwable) {}
			try { am.mode = state.mode } catch (_: Throwable) {}
		} catch (_: Throwable) {}
	}

	private fun speakerStopInternal() {
		try {
			speakerPlayer?.setOnCompletionListener(null)
			speakerPlayer?.setOnPreparedListener(null)
			speakerPlayer?.stop()
		} catch (_: Throwable) {}
		try {
			speakerPlayer?.release()
		} catch (_: Throwable) {}
		speakerPlayer = null

		val t = speakerToken
		speakerToken = null
		if (t != null) {
			endSpeakerRoute(t)
		}
	}

	private fun speakerPlayUrl(url: String, volume: Double) {
		speakerStopInternal()

		val token = beginSpeakerRoute()
		speakerToken = token

		val v = volume.coerceIn(0.0, 1.0).toFloat()
		val mp = MediaPlayer()
		speakerPlayer = mp
		try {
			mp.setAudioAttributes(
				AudioAttributes.Builder()
					.setUsage(AudioAttributes.USAGE_VOICE_COMMUNICATION)
					.setContentType(AudioAttributes.CONTENT_TYPE_SPEECH)
					.build()
			)
			mp.setDataSource(url)
			mp.setOnPreparedListener {
				try {
					it.setVolume(v, v)
					it.start()
				} catch (_: Throwable) {
					speakerStopInternal()
				}
			}
			mp.setOnCompletionListener {
				speakerStopInternal()
			}
			mp.prepareAsync()
		} catch (_: Throwable) {
			speakerStopInternal()
		}
	}

	override fun configureFlutterEngine(flutterEngine: FlutterEngine) {
		super.configureFlutterEngine(flutterEngine)

		MethodChannel(flutterEngine.dartExecutor.binaryMessenger, channelName).setMethodCallHandler { call, result ->
			when (call.method) {
				"start" -> {
					val username = call.argument<String>("tiktokUsername")
					ForegroundService.start(this, username)
					result.success(null)
				}
					"showOverlay" -> {
						ForegroundService.showOverlay(this)
						result.success(null)
					}
					"hideOverlay" -> {
						ForegroundService.hideOverlay(this)
						result.success(null)
					}
				"stop" -> {
					ForegroundService.stop(this)
					result.success(null)
				}
				"audioRouteBegin" -> {
					val route = (call.argument<String>("route") ?: "").trim()
					if (route == "speaker") {
						val token = beginSpeakerRoute()
						result.success(token)
					} else {
						result.success(null)
					}
				}
				"audioRouteEnd" -> {
					val token = call.argument<Int>("token")
					if (token != null) {
						endSpeakerRoute(token)
					}
					result.success(null)
				}
				"speakerPlayUrl" -> {
					val url = call.argument<String>("url")
					val volume = call.argument<Double>("volume") ?: 1.0
					if (url != null && url.isNotBlank()) {
						speakerPlayUrl(url.trim(), volume)
					}
					result.success(null)
				}
				"speakerStop" -> {
					speakerStopInternal()
					result.success(null)
				}
				else -> result.notImplemented()
			}
		}
	}
}
