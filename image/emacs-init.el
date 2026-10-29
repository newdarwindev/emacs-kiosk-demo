(setq inhibit-startup-screen t
      initial-scratch-message nil
      ring-bell-function 'ignore
      make-backup-files nil
      auto-save-default nil)
(menu-bar-mode -1)
(tool-bar-mode -1)
(scroll-bar-mode -1)
(set-face-attribute 'default nil :family "DejaVu Sans Mono" :height 160)
(set-face-attribute 'default nil :background "#101a26" :foreground "#e5edf5")
(set-face-attribute 'mode-line nil :background "#9de2c3" :foreground "#101a26" :box nil)
(setq-default mode-line-format '("  EMACS KIOSK  |  OFFLINE DEMO     " "%b" "     " mode-name))
(setq frame-title-format "EMACS KIOSK - offline demo")
(add-hook 'emacs-startup-hook (lambda () (goto-char (point-min))))
