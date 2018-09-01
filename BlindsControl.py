import appdaemon.plugins.hass.hassapi as hass
from datetime import datetime, timedelta
import traceback
from threading import Semaphore
import re
import os
import inspect


class BlindsControl(hass.Hass):

    def initialize(self):
        self._lock = Semaphore(1)
        nextrun = datetime.now() + timedelta(seconds=10)
        # run over all covers an check if configurations are available
        # then start the spcific handlers for each covers
        statedict = self.get_state()
        self._coverdict = dict()
        changeduration = 10
        for entity in statedict:
            if re.match('^cover.*', entity, re.IGNORECASE):
                # detected cover
                id = self._getid(statedict, entity)
                handledict = dict()
                # create listeners for config changes
                for configvar in BlindsControlConfiguration.variables_boolean:
                    cvarname = "input_boolean.control_blinds_%s_%s" % (
                        id, configvar)
                    if self.entity_exists(cvarname):
                        handle = self.listen_state(
                            self._config_change, cvarname, entityid=id, duration=changeduration)
                        handledict.update({cvarname: handle})
                for configvar in BlindsControlConfiguration.variables_number:
                    cvarname = "input_number.control_blinds_%s_%s" % (
                        id, configvar)
                    if self.entity_exists(cvarname):
                        handle = self.listen_state(
                            self._config_change, cvarname, entityid=id, duration=changeduration)
                        handledict.update({cvarname: handle})
                for configvar in BlindsControlConfiguration.variables_datetime:
                    cvarname = "input_datetime.control_blinds_%s_%s" % (
                        id, configvar)
                    if self.entity_exists(cvarname):
                        handle = self.listen_state(
                            self._config_change, cvarname, entityid=id, duration=changeduration)
                        handledict.update({cvarname: handle})

                # create variables per cover
                vardict = dict()
                vardict.update({"time_close_blinds": None})
                vardict.update({"time_open_blinds": None})
                vardict.update({"coverID": entity})

                # create open blinds handle
                if len(handledict) > 0:
                    ob_handle = None
                    self._log_debug("input_boolean.control_blinds_%s_openblinds: %s" % (id,self.get_state("input_boolean.control_blinds_%s_openblinds" % id)),prefix=id)
                    self._log_debug("input_boolean.control_blinds_enable_global: %s" % (self.get_state("input_boolean.control_blinds_enable_global")),prefix=id)
                    if (self.get_state("input_boolean.control_blinds_%s_openblinds" % id)=="on" and self.get_state("input_boolean.control_blinds_enable_global")=="on"):
                        ob_handle = self.run_at(
                            self._choose_open_blinds_method, datetime.now() + timedelta(seconds=5), entityid=id)
                    handledict.update({"ob_handle": ob_handle})

                    # create close blinds handle
                    cb_handle = None
                    self._log_debug("input_boolean.control_blinds_%s_closeblinds: %s" % (id,self.get_state("input_boolean.control_blinds_%s_closeblinds" % id)),prefix=id)
                    self._log_debug("input_boolean.control_blinds_enable_global: %s" % (self.get_state("input_boolean.control_blinds_enable_global")),prefix=id)
                    if (self.get_state("input_boolean.control_blinds_%s_closeblinds" % id)=="on" and self.get_state("input_boolean.control_blinds_enable_global")=="on"):
                        cb_handle = self.run_at(
                            self._choose_close_blinds_method, datetime.now() + timedelta(seconds=5), entityid=id)
                    handledict.update({"cb_handle": cb_handle})

                    # create open/close blinds handle for cooldown
                    obcd_handle = None
                    cbcd_handle = None
                    self._log_debug("input_boolean.control_blinds_%s_cooldown_during_night: %s" % (id,self.get_state("input_boolean.control_blinds_%s_cooldown_during_night" % id)),prefix=id)
                    self._log_debug("input_boolean.control_blinds_enable_global: %s" % (self.get_state("input_boolean.control_blinds_enable_global")),prefix=id)
                    self._log_debug("input_boolean.control_blinds_enable_cooldown_during_night_global: %s" % (self.get_state("input_boolean.control_blinds_enable_cooldown_during_night_global")),prefix=id)
                    if (self.get_state("input_boolean.control_blinds_%s_cooldown_during_night" % id)=="on" and self.get_state("input_boolean.control_blinds_enable_global")=="on" and self.get_state("input_boolean.control_blinds_enable_cooldown_during_night_global")=="on"):
                        obcd_handle = self.run_at(
                            self._open_blinds_cooldown, datetime.now() + timedelta(seconds=5), entityid=id)
                        cbcd_handle = self.run_at(
                            self._close_blinds_cooldown, datetime.now() + timedelta(seconds=5), entityid=id)
                    handledict.update({"obcd_handle": obcd_handle})
                    handledict.update({"cbcd_handle": cbcd_handle})

                    d = dict()
                    d.update({"handledict": handledict})
                    d.update({"vardict": vardict})
                    self._coverdict.update({id: d})

        # add global config handlers
        handledict = dict()
        for configvar in BlindsControlConfiguration.variables_boolean_global:
            cvarname = "input_boolean.control_blinds_%s_global" % configvar
            if self.entity_exists(cvarname):
                handle = self.listen_state(
                    self._config_change, cvarname, duration=changeduration)
                handledict.update({cvarname: handle})
        d = dict()
        d.update({"handledict": handledict})
        self._coverdict.update({"global": d})

    def _get_handle(self, entityid, handle):
        edict = self._coverdict.get(entityid, dict())
        handledict = edict.get('handledict', dict())
        return handledict.get(handle, None)

    def _set_handle(self, entityid, varname, handle):
        edict = self._coverdict.get(entityid, dict())
        handledict = edict.get('handledict', dict())
        handledict.update({varname: handle})
        edict.update({"handledict": handledict})

    def _get_variable(self, entityid, varname):
        edict = self._coverdict.get(entityid, dict())
        vardict = edict.get('vardict', dict())
        self._log_debug("entityid: %s, varname: %s, len(edict):%s, len(vardict):%s" % (entityid,varname,len(edict),len(vardict)))
        return vardict.get(varname, None)

    def _set_variable(self, entityid, varname, value):
        edict = self._coverdict.get(entityid, dict())
        vardict = edict.get('vardict', dict())
        vardict.update({varname: value})
        edict.update({"vardict": vardict})

    def _config_change(self, entity, attribute, old, new, kwargs):
        try:
            self._lock.acquire(True)
            entityid = kwargs.get('entityid', None)
            self._log_debug("config_change",prefix=entityid)
            # cancel and create new open blinds handle
            ob_handle = self._get_handle(entityid, 'ob_handle')
            if ob_handle is not None:
                self.cancel_timer(ob_handle)
                ob_handle = None
            if (self.get_state("input_boolean.control_blinds_%s_openblinds" % entityid)=="on" and self.get_state("input_boolean.control_blinds_enable_global")=="on"):
                ob_handle = self.run_at(
                    self._choose_open_blinds_method, datetime.now() + timedelta(seconds=5), entityid=entityid)
            else:
                self._log("Control Blinds global or per cover is disabled (Open Blinds: %s, Control Blinds Global: %s)" % (self.get_state(
                    "input_boolean.control_blinds_%s_openblinds" % entityid), self.get_state("input_boolean.control_blinds_enable_global")),prefix=entityid)
            self._set_handle(entityid, "ob_handle", ob_handle)

            # create close blinds handle
            cb_handle = self._get_handle(entityid, 'cb_handle')
            if cb_handle is not None:
                self.cancel_timer(cb_handle)
                cb_handle = None
            if (self.get_state("input_boolean.control_blinds_%s_closeblinds" % entityid)=="on" and self.get_state("input_boolean.control_blinds_enable_global")=="on"):
                cb_handle = self.run_at(
                    self._choose_close_blinds_method, datetime.now() + timedelta(seconds=5), entityid=entityid)
            else:
                self._log("Control Blinds global or per cover is disabled (Close Blinds: %s, Control Blinds Global: %s)" % (self.get_state(
                    "input_boolean.control_blinds_%s_closeblinds" % entityid), self.get_state("input_boolean.control_blinds_enable_global")),prefix=entityid)
            self._set_handle(entityid, "cb_handle", cb_handle)

            # create open blinds handle for cooldown
            obcd_handle = self._get_handle(entityid, 'obcd_handle')
            cbcd_handle = self._get_handle(entityid, 'cbcd_handle')
            if obcd_handle is not None:
                self.cancel_timer(obcd_handle)
                obcd_handle = None
            if cbcd_handle is not None:
                self.cancel_timer(cbcd_handle)
                cbcd_handle = None
            if (self.get_state("input_boolean.control_blinds_%s_cooldown_during_night" % id)=="on" and self.get_state("input_boolean.control_blinds_enable_global")=="on" and self.get_state("input_boolean.control_blinds_enable_cooldown_during_night_global")=="on"):
                obcd_handle = self.run_at(
                    self._open_blinds_cooldown, datetime.now() + timedelta(seconds=5), entityid=entityid)
                cbcd_handle = self.run_at(
                    self._close_blinds_cooldown, datetime.now() + timedelta(seconds=5), entityid=entityid)
            else:
                self._log("Control Blinds global or per cover is disabled (Cooldown During  Blinds: %s, Control Blinds During Night Global: %s, Control Blinds Global: %s)" % (self.get_state(
                    "input_boolean.control_blinds_%s_cooldown_during_night" % id), self.get_state("input_boolean.control_blinds_enable_cooldown_during_night_global"), self.get_state("input_boolean.control_blinds_enable_global")),prefix=entityid)
            self._set_handle(entityid, "obcd_handle", obcd_handle)
            self._set_handle(entityid, "cbcd_handle", cbcd_handle)
        except:
            entityid = kwargs.get('entityid', None)
            self._log_error(traceback.format_exc(),prefix=entityid)
        finally:
            self._lock.release()

    def _choose_close_blinds_method(self, kwargs):
        # decide which mode is currently used. sunset mode or time based mode
        try:
            self._lock.acquire(True)
            entityid = kwargs.get('entityid', None)
            self._set_variable(entityid, "time_close_blinds", None)
            if self.get_state("input_boolean.control_blinds_%s_sunsetsunrise" % entityid) == "on":
                self._log(
                    "control blind according to sunset/sunrise enabled",prefix=entityid)
                self._close_blinds_sun(entityid)
            else:
                self._log(
                    "control blind according to time enabled",prefix=entityid)
                self._close_blinds_time(entityid)
        except:
            entityid = kwargs.get('entityid', None)
            self._log_error(traceback.format_exc(),prefix=entityid)
            nexttrigger = datetime.now() + timedelta(seconds=5)
            self._log_error("close_blinds: Catched Error. Restart at %s" %
                        nexttrigger,prefix=entityid)
            self._set_variable(entityid, "time_close_blinds", None)
            self._set_handle(entityid, "cb_handle", self.run_at(
                self._close_blinds, datetime.now() + timedelta(seconds=5), entityid=entityid))
        finally:
            self._lock.release()

    def _close_blinds_cooldown(self, kwargs):
        try:
            self._lock.acquire(True)
            entityid = kwargs.get('entityid', None)
            self._set_handle(entityid, "cbcd_handle", None)
            self._log("Close Blinds Cooldown",prefix=entityid)
            today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
            # Zeit für das schließen der Blinds bestimmen. Wenn die Zeit NACH der aktuellen Zeit für das öffnen der Blinds ist nichts machen. Dann ist die Konfiguration falsch.
            cooldownnightdown = today + timedelta(hours=self.get_state("input_datetime.control_blinds_%s_cooldown_during_night_close" % entityid, attribute="hour"), minutes=self.get_state(
                "input_datetime.control_blinds_%s_cooldown_during_night_close" % entityid, attribute="minute"), seconds=self.get_state("input_datetime.control_blinds_%s_cooldown_during_night_close" % entityid, attribute="second"))
            # wenn die Stunde zwischen 12 und 24 Uhr lieg muss kein Tag drauf adiert werden. Ansonsten gehe ich davon aus, dass die Urhzeit sich auf den nächsten Tag bezieht
            if self.get_state("input_datetime.control_blinds_%s_cooldown_during_night_close" % entityid, attribute="hour") < 12 and datetime.now().hour >= 12:
                cooldownnightdown += timedelta(days=1)
            self._log("close_blinds_cooldown: cooldownnightdown: %s" %
                      cooldownnightdown,prefix=entityid)
            if cooldownnightdown < datetime.now():
                # zeit vorbei nicht machen und warten bis zum nächsten Tag
                self._log(
                    "close_blinds_cooldown: Zeit ist schon vorbei. Warten bis zum nächsten Tag",prefix=entityid)
                self._set_handle(entityid, "cbcd_handle", self.run_at(
                    self._close_blinds_cooldown_, today + timedelta(days=1, minutes=5), entityid=entityid))
            else:
                if self.get_state("input_boolean.control_blinds_%s_openblinds" % entityid)=="on" and (self._get_variable(entityid, "time_open_blinds") is None or cooldownnightdown > self.time_open_blinds):
                    # Entweder ist die Konfiguration kaputt oder wir haben noch die alte Zeit vom Vortag
                    self._log(
                        "close_blinds_cooldown: cooldownnightdown<self.time_open_blinds. check again in 5 minutes",prefix=entityid)
                    self._log("close_blinds_cooldown: cooldownnightdown: %s" %
                              cooldownnightdown,prefix=entityid)
                    self._log("close_blinds_cooldown: self.time_open_blinds: %s" %
                              self._get_variable(entityid, "time_open_blinds"),prefix=entityid)
                    self._set_handle(entityid, "cbcd_handle", self.run_at(
                        self._close_blinds_cooldown_, datetime.now() + timedelta(minutes=5), entityid=entityid))
                else:
                    self._log("close_blinds_cooldown: Trigger cooldownnightdown: %s" %
                              cooldownnightdown,prefix=entityid)
                    self._set_handle(entityid, "cbcd_handle", self.run_at(
                        self._close_blinds_cooldown_, cooldownnightdown, entityid=entityid))
        except:
            entityid = kwargs.get('entityid', None)
            self._log_error(traceback.format_exc(),prefix=entityid)
            nexttrigger = datetime.now() + timedelta(seconds=5)
            self._log_error("close_blinds_cooldown: Catched Error. Restart in %s" %
                        nexttrigger,prefix=entityid)
            self._set_handle(entityid, "cbcd_handle", self.run_at(
                self._close_blinds_cooldown, datetime.now() + timedelta(seconds=5), entityid=entityid))
        finally:
            self._lock.release()

    def _choose_open_blinds_method(self, kwargs):
        try:
            self._lock.acquire(True)
            entityid = kwargs.get('entityid', None)
            self._set_handle(entityid, "ob_handle", None)
            self._set_variable(entityid, "time_open_blinds", None)
            # Entscheiden welcher Modus aktuell aktiviert ist
            if self.get_state("input_boolean.control_blinds_%s_sunsetsunrise" % entityid) == "on":
                self._log(
                    "control blind according to sunset/sunrise enabled",prefix=entityid)
                self._open_blinds_sun(entityid)
            else:
                self._log(
                    "control blind according to time enabled",prefix=entityid)
                self._open_blinds_time(entityid)
        except:
            entityid = kwargs.get('entityid', None)
            self._log_error(traceback.format_exc(),prefix=entityid)
            nexttrigger = datetime.now() + timedelta(seconds=5)
            self._log_error("open_blinds: Catched Error. Restart in %s" %
                        nexttrigger,prefix=entityid)
            self._set_variable(entityid, "time_open_blinds", None)
            self._set_handle(entityid, "ob_handle", self.run_at(
                self._choose_open_blinds_method, datetime.now() + timedelta(seconds=5), entityid=entityid))
        finally:
            self._lock.release()

    def _open_blinds_cooldown(self, kwargs):
        try:
            self._lock.acquire(True)
            entityid = kwargs.get('entityid', None)
            self._set_handle(entityid, "obcd_handle", None)
            today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
            # Zeit für das öffnen der Blinds bestimmen. Wenn die Zeit VOR der aktuellen Zeit für das schließen der Blinds ist nichts machen. Dann ist die Konfiguration falsch.
            cooldownnightup = today + timedelta(hours=self.get_state("input_datetime.control_blinds_%s_cooldown_during_night_open" % entityid, attribute="hour"), minutes=self.get_state(
                "input_datetime.control_blinds_%s_cooldown_during_night_open" % entityid, attribute="minute"), seconds=self.get_state("input_datetime.control_blinds_%s_cooldown_during_night_open" % entityid, attribute="second"))
            # wenn die Stunde zwischen 12 und 24 Uhr lieg muss kein Tag drauf adiert werden. Ansonsten gehe ich davon aus, dass die Urhzeit sich auf den nächsten Tag bezieht
            if self.get_state("input_datetime.control_blinds_%s_cooldown_during_night_open" % entityid, attribute="hour") < 12 and datetime.now().hour >= 12:
                cooldownnightup += timedelta(days=1)
            self._log("open_blinds_cooldown: cooldownnightup: %s" %
                      cooldownnightup,prefix=entityid)
            if cooldownnightup < datetime.now():
                # Zeit ist schon vorbei, warten bis zum nächsten Tag
                self._log(
                    "open_blinds_cooldown: Zeit ist schon vorbei. Warten bis zum nächsten Tag",prefix=entityid)
                self._set_handle(entityid, "obcd_handle", self.run_at(
                    self._open_blinds_cooldown, today + timedelta(days=1, minutes=5), entityid=entityid))
            else:
                if self.get_state("input_boolean.control_blinds_%s_closeblinds" % entityid)=="on" and (self._get_variable(entityid, "time_close_blinds") is None or cooldownnightup < self._get_variable(entityid, "time_close_blinds")):
                    # entweder die Konfiguration ist kaputt oder aktuell haben wir noch die alte Zeit vom Vortag.
                    # wir machen nichts und prüfen starten in 5 min neu
                    self._log(
                        "open_blinds_cooldown: cooldownnightup<self.time_close_blinds. check again in 5 minutes",prefix=entityid)
                    self._log("open_blinds_cooldown: cooldownnightup: %s" %
                              cooldownnightup,prefix=entityid)
                    self._log("open_blinds_cooldown: self.time_close_blinds: %s" %
                              self._get_variable(entityid, "timeclose_blinds"),prefix=entityid)
                    self._set_handle(entityid, "obcd_handle", self.run_at(
                        self._open_blinds_cooldown, datetime.now() + timedelta(minutes=5), entityid=entityid))
                else:
                    self._log("open_blinds_cooldown: Trigger cooldownnightup: %s" % cooldownnightup,prefix=entityid)
                    self._set_handle(entityid, "obcd_handle", self.run_at(
                        self._open_blinds_cooldown, cooldownnightup, entityid=entityid))
        except:
            entityid = kwargs.get('entityid', None)
            self._log_error(traceback.format_exc(),prefix=entityid)
            nexttrigger = datetime.now() + timedelta(seconds=5)
            self._log_error("open_blinds: Catched Error. Restart in %s" %
                        nexttrigger,prefix=entityid)
            self._set_handle(entityid, "obcd_handle", self.run_at(
                self._open_blinds_cooldown, datetime.now() + timedelta(seconds=5), entityid=entityid))
        finally:
            self._lock.release()

    def _close_blinds_sun(self, entityid):
        sunset_offset = timedelta(hours=self.get_state("input_datetime.control_blinds_%s_offset_blinds_down_after_sunset" % entityid, attribute="hour"), minutes=self.get_state(
            "input_datetime.control_blinds_%s_offset_blinds_down_after_sunset" % entityid, attribute="minute"), seconds=self.get_state("input_datetime.control_blinds_%s_offset_blinds_down_after_sunset" % entityid, attribute="second"))
        sunset = self.sunset()
        sunsetday = sunset.replace(
            hour=0, minute=0, second=0, microsecond=0)
        self._log_debug("close_blinds_sun: Sunsetday: %s" % sunsetday,prefix=entityid)
        self._log_debug("close_blinds_sun: Sunset: %s" % sunset,prefix=entityid)
        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        self._log_debug("close_blinds_sun: Today: %s" % today,prefix=entityid)
        ltbds = timedelta(hours=self.get_state("input_datetime.control_blinds_%s_latest_time_blinds_down" % entityid, attribute="hour"), minutes=self.get_state(
            "input_datetime.control_blinds_%s_latest_time_blinds_down" % entityid, attribute="minute"), seconds=self.get_state("input_datetime.control_blinds_%s_latest_time_blinds_down" % entityid, attribute="second"))
        self._log_debug("close_blinds_sun: ltbds: %s" % ltbds,prefix=entityid)
        latesttimedown = today + ltbds
        self._log_debug("close_blinds_sun: LatesttimeDown: %s" % latesttimedown,prefix=entityid)
        if sunsetday == today:
            # sunset is today and not tomorrow (already passed sunset)
            sunsettime = sunset + sunset_offset
            self._log_debug(
                "close_blinds_sun: Sunsettime: %s" % sunsettime,prefix=entityid)
            # wenn sunset + offset nach latesttimedown ist, nehmen wir latesttimedown als sunset
            if sunsettime > latesttimedown:
                sunsettime = latesttimedown
            self._log_debug(
                "close_blinds_sun: Sunsettime: %s" % sunsettime,prefix=entityid)
            self._log_debug("close_blinds_sun: Now: %s" % datetime.now(),prefix=entityid)
            if sunsettime < datetime.now():
                # Zeit ist schon vorbei. Nichts tun. Warten und neu prüfen, bis sich sunsettime geändert hat..
                # Trigger neu starten
                self._log(
                    "close_blinds_sun: sunsettime has passed, wait till next day",prefix=entityid)
                self._set_handle(entityid, "cb_handle", self.run_at(
                    self._close_blinds, datetime.now() + timedelta(minutes=5), entityid=entityid))
            else:
                # sunset time ist in der Zukunft. Trigger zum schließen starten
                self._log(
                    "close_blinds_sun: sunset is in the future {}".format(sunsettime),prefix=entityid)
                self._set_variable(entityid, "time_close_blinds", sunsettime)
                self._set_handle(entityid, "cb_handle", self.run_at(
                    self._close_blinds, sunsettime, entityid=entityid))
        else:
            # sonnenuntergang ist am nächsten Tag. Warten bis zum nächsten Tag.
            # Trigger neu starten
            if sunsetday < today:
                # hier sollten wir nie landen
                self._log(
                    "close_blinds_sun: sunsetday<today, check again shortly",prefix=entityid)
                self._set_handle(entityid, "cb_handle", self.run_at(
                    self._close_blinds, datetime.now() + timedelta(minutes=5), entityid=entityid))
            else:
                nexttrigger = sunsetday + timedelta(minutes=5)
                self._log(
                    "close_blinds_sun: sunset has passed, wait for next day %s" % nexttrigger,prefix=entityid)
                self._set_handle(entityid, "cb_handle", self.run_at(
                    self._choose_close_blinds_method, nexttrigger, entityid=entityid))

    def _close_blinds_time(self, entityid):
        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        self._log_debug("close_blinds_time: Today: %s" % today,prefix=entityid)
        tbd = timedelta(hours=self.get_state("input_datetime.control_blinds_%s_closeblinds_on_time" % entityid, attribute="hour"), minutes=self.get_state(
            "input_datetime.control_blinds_%s_closeblinds_on_time" % entityid, attribute="minute"), seconds=self.get_state("input_datetime.control_blinds_%s_closeblinds_on_time" % entityid, attribute="second"))
        self._log_debug("close_blinds_time: tbd: %s" % tbd,prefix=entityid)
        timedown = today + tbd
        self._log_debug("close_blinds_time: timeDown: %s" % timedown,prefix=entityid)
        if timedown < datetime.now():
            # Zeit ist schon vorbei. Warten bis zum nächsten Tag.
            # Trigger neu starten
            self._log(
                "close_blinds_time: timedown has passed, wait till next day",prefix=entityid)
            self._set_handle(entityid, "cb_handle", self.run_at(
                self._choose_close_blinds_method, today + timedelta(days=1, minutes=5), entityid=entityid))
        else:
            # timedown ist in der Zukunft. Trigger zum schließen starten
            self._log(
                "close_blinds_time: timedown is in the future %s" % timedown,prefix=entityid)
            self._set_variable(entityid, "time_close_blinds", timedown)
            self._set_handle(entityid, "cb_handle", self.run_at(
                self._close_blinds, timedown, entityid=entityid))

    def _close_blinds(self, kwargs):
        try:
            self._lock.acquire(True)
            entityid = kwargs.get('entityid', None)
            self._set_handle(entityid, "cb_handle", None)
            # cover stand lesen und dann ggf nochmal schließen
            self._log_debug("_Cover State: %s/%s" % (self.get_state(
                self._get_variable(entityid, "coverID")), self.get_state(self._get_variable(entityid, "coverID"), attribute="current_position")),prefix=entityid)
            self._log_debug("use_pd_on_close %s" % self.get_state(
                "input_boolean.control_blinds_%s_use_pd_on_close" % entityid),prefix=entityid)
            if not self.get_state("input_boolean.control_blinds_%s_use_pd_on_close" % entityid)=="on" or (self.get_state("input_boolean.control_blinds_%s_use_pd_on_close" % entityid)=="on" and not self.anyone_home()):
                if self.get_state(self._get_variable(entityid, "coverID"), attribute="current_position") > 0:
                    self._log("close cover %s" %
                              self._get_variable(entityid, "coverID"),prefix=entityid)
                    self.call_service("cover/close_cover",
                                      entity_id=self._get_variable(entityid, "coverID"))
            else:
                # je nach einstellung beachten wir ob jemand zu Hause ist
                # Es ist jemand zu Hause und wir sollen das beachten
                self._log(
                    "Do not close blinds while someone is at home",prefix=entityid)
            # Trigger neu starten
            self._log("nexttrigger %s" %
                      (datetime.now() + timedelta(minutes=5)),prefix=entityid)
            self._set_variable(entityid, "time_close_blinds", None)
            self._set_handle(entityid, "cb_handle", self.run_at(
                self._choose_close_blinds_method, datetime.now() + timedelta(minutes=5), entityid=entityid))
        except:
            entityid = kwargs.get('entityid', None)
            self._log_error(traceback.format_exc(),prefix=entityid)
            nexttrigger = datetime.now() + timedelta(seconds=5)
            self._log_error("close_blinds: Catched Error. Restart in %s" %
                        nexttrigger,prefix=entityid)
            self._set_handle(entityid, "cb_handle", self.run_at(
                self._choose_close_blinds_method, datetime.now() + timedelta(seconds=5), entityid=entityid))
        finally:
            self._lock.release()

    def _close_blinds_cooldown_(self, kwargs):
        try:
            self._lock.acquire(True)
            entityid = kwargs.get('entityid', None)
            self._set_handle(entityid, "cbcd_handle", None)
            self._log_debug("Cover State: %s/%s" % (self.get_state(
                self._get_variable(entityid, "coverID")), self.get_state(self._get_variable(entityid, "coverID"), attribute="current_position")),prefix=entityid)
            if self.get_state(self._get_variable(entityid, "coverID"), attribute="current_position") > 0:
                self._log("close cover %s" %
                          self._get_variable(entityid, "coverID"),prefix=entityid)
                self.call_service("cover/close_cover",
                                  entity_id=self._get_variable(entityid, "coverID"))
            self._log("nexttrigger %s" %
                      (datetime.now() + timedelta(minutes=5)),prefix=entityid)
            self._set_handle(entityid, "cbcd_handle", self.run_at(
                self._close_blinds_cooldown, datetime.now() + timedelta(minutes=5), entityid=entityid))
        except:
            entityid = kwargs.get('entityid', None)
            self._log_error(traceback.format_exc(),prefix=entityid)
            nexttrigger = datetime.now() + timedelta(seconds=5)
            self._log_error("Catched Error. Restart in %s" %
                        nexttrigger,prefix=entityid)
            self._set_handle(entityid, "cbcd_handle", self.run_at(
                self._close_blinds_cooldown, datetime.now() + timedelta(seconds=5), entityid=entityid))
        finally:
            self._lock.release()

    def _open_blinds_sun(self, entityid):
        sunrise_buw_offset_dtime = datetime.strptime("%s" %
                                                     self.get_state("input_datetime.control_blinds_%s_offset_blinds_up_weekend" % entityid), "%H:%M:%S")
        sunrise_buw_offset = timedelta(hours=sunrise_buw_offset_dtime.hour,
                                       minutes=sunrise_buw_offset_dtime.minute, seconds=sunrise_buw_offset_dtime.second)
        self._log_debug("Offset Blinds Up Weekend %s" % sunrise_buw_offset,prefix=entityid)
        # Sonnenaufgang pruefen
        sunrise = self.sunrise()
        sunriseday = sunrise.replace(
            hour=0, minute=0, second=0, microsecond=0)
        self._log_debug("Sunriseday: %s" % sunriseday,prefix=entityid)
        self._log_debug("Sunrise: %s" % sunrise,prefix=entityid)
        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        self._log_debug("Today: %s" % today,prefix=entityid)
        etbus_dtime = datetime.strptime("%s" % self.get_state(
            "input_datetime.control_blinds_%s_earliest_time_blinds_up" % entityid), "%H:%M:%S")
        etbus = timedelta(
            hours=etbus_dtime.hour, minutes=etbus_dtime.minute, seconds=etbus_dtime.second)
        self._log_debug("etbus: %s" % etbus,prefix=entityid)
        earliesttimeup = today + etbus
        self._log_debug("Earliesttimeup: %s" %
                  earliesttimeup,prefix=entityid)
        sunrisetime = sunrise
        self._log_debug("Sunrisetime: %s" % sunrisetime,prefix=entityid)
        if sunriseday == today:
            # sonnenaufgang ist heute
            if self.get_state("binary_sensor.workday_sensor") == "off":
                # kein werktag. offset anwenden
                sunrisetime += sunrise_buw_offset
                self._log_debug("Offset Blinds Up Weekend %s" %
                          sunrise_buw_offset,prefix=entityid)
                self._log_debug("Weekend detected. Add offeset to sunrise time. New sunrise time: %s" %
                          sunrisetime,prefix=entityid)
            # wenn sunrise vor earliest time up, nehmen wir earliesttime up
            if sunrisetime < earliesttimeup:
                sunrisetime = earliesttimeup
                self._log_debug(
                    "Sunrisetime: %s" % sunrisetime,prefix=entityid)
            if sunrisetime < datetime.now():
                # Sunrise time ist schon verstrichen, warten und neu pruefen
                self._log(
                    "sunrise time passed, retry shortly",prefix=entityid)
                self._set_handle(entityid, "ob_handle", self.run_at(
                    self._open_blinds, datetime.now() + timedelta(minutes=5), entityid=entityid))
            else:
                # sunrise ist in de zukunft. Trigger starten
                self._log(
                    "sunrise in future at %s" % sunrisetime,prefix=entityid)
                self._set_variable(entityid, "time_open_blinds", sunrisetime)
                self._set_handle(entityid, "ob_handle", self.run_at(
                    self._open_blinds, sunrisetime, entityid=entityid))
        else:
            # sunrise ist am nächsten Tag , warten bis zum nächsten Tag
            if sunriseday < today:
                # hier sollten wir nie landen
                self._log(
                    "sunriseday<today, retry shortly",prefix=entityid)
                self._set_handle(entityid, "ob_handle", self.run_at(
                    self._open_blinds, datetime.now() + timedelta(minutes=5), entityid=entityid))
            else:
                # wir muessen wegen dem unterschied lokaler Zeit zu UTC aufpassen
                nexttrigger = sunriseday + timedelta(minutes=5)
                self._log(
                    "sunrise has passed wait for next day %s" % nexttrigger,prefix=entityid)
                self._set_handle(entityid, "ob_handle", self.run_at(
                    self._choose_open_blinds_method, nexttrigger,entityid=entityid))

    def _open_blinds_time(self, entityid):
        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        self._log_debug("open_blinds_time: Today: %s" % today,prefix=entityid)
        tbu = timedelta(hours=self.get_state("input_datetime.control_blinds_%s_openblinds_on_time" % entityid, attribute="hour"), minutes=self.get_state(
            "input_datetime.control_blinds_%s_openblinds_on_time" % entityid, attribute="minute"), seconds=self.get_state("input_datetime.control_blinds_%s_openblinds_on_time" % entityid, attribute="second"))
        self._log_debug("open_blinds_time: tbu: %s" % tbu,prefix=entityid)
        timeup = today + tbu
        self._log_debug("open_blinds_time: timeup: %s" % timeup,prefix=entityid)
        if timeup < datetime.now():
            # Zeit ist schon vorbei. Nichts tun. Warten bis zum nächsten Tag und neu prüfen.
            # Trigger neu starten
            self._log(
                "open_blinds_time: timeup has passed, wait till next day",prefix=entityid)
            self._set_handle(entityid, "ob_handle", self.run_at(
                self._choose_open_blinds_method, today + timedelta(days=1, minutes=5), entityid=entityid))
        else:
            # timedown ist in der Zukunft. Trigger zum schließen starten
            self._log(
                "open_blinds_time: timeup is in the future %s" % timeup,prefix=entityid)
            self._set_variable(entityid, "time_open_blinds", timeup)
            self._set_handle(entityid, "ob_handle", self.run_at(
                self._open_blinds, timeup, entityid=entityid))

    def _open_blinds(self, kwargs):
        try:
            self._lock.acquire(True)
            entityid = kwargs.get('entityid', None)
            self._set_handle(entityid, "ob_handle", None)
            # cover stand lesen und dann ggf oeffnen
            self._log_debug("Cover State: %s/%s" % (self.get_state(
                self._get_variable(entityid, "coverID")), self.get_state(self._get_variable(entityid, "coverID"), attribute="current_position")),prefix=entityid)
            if self.get_state(self._get_variable(entityid, "coverID"), attribute="current_position") < 100:
                self._log("open cover %s" %
                          self._get_variable(entityid, "coverID"),prefix=entityid)
                self.call_service("cover/open_cover",
                                  entity_id=self._get_variable(entityid, "coverID"))
            # Trigger neu starten
            self._log("nexttrigger %s" %
                      (datetime.now() + timedelta(minutes=5)),prefix=entityid)
            self._set_variable(entityid, "time_open_blinds", None)
            self._set_handle(entityid, "ob_handle", self.run_at(
                self._choose_open_blinds_method, datetime.now() + timedelta(minutes=5), entityid=entityid))
        except:
            entityid = kwargs.get('entityid', None)
            self._log_error(traceback.format_exc(),prefix=entityid)
            nexttrigger = datetime.now() + timedelta(seconds=5)
            self._log_error("Catched Error. Restart in %s" %
                        nexttrigger,prefix=entityid)
            self._set_handle(entityid, "ob_handle", self.run_at(
                self._choose_open_blinds_method, datetime.now() + timedelta(seconds=5), entityid=entityid))
        finally:
            self._lock.release()

    def _open_blinds_cooldown_(self, kwargs):
        try:
            self._lock.acquire(True)
            entityid = kwargs.get('entityid', None)
            self._set_handle(entityid, "obcd_handle", None)
            self._log_debug("_open_blinds_cooldown: Cover State: %s/%s" % (self.get_state(
                self._get_variable(entityid, "coverID")), self.get_state(self._get_variable(entityid, "coverID"), attribute="current_position")),prefix=entityid)
            if self.get_state(self._get_variable(entityid, "coverID"), attribute="current_position") < 100:
                self._log("_open_blinds_cooldown: open cover %s" %
                          self._get_variable(entityid, "coverID"),prefix=entityid)
                self.call_service("cover/open_cover",
                                  entity_id=self._get_variable(entityid, "coverID"))
            # Trigger neu starten
            self._log("_open_blinds_cooldown: nexttrigger %s" %
                      datetime.now() + timedelta(minutes=5),prefix=entityid)
            self._set_handle(entityid, "obcd_handle", self.run_at(
                self._open_blinds_cooldown, datetime.now() + timedelta(minutes=5), entityid=entityid))
        except:
            entityid = kwargs.get('entityid', None)
            self._log_error(traceback.format_exc(),prefix=entityid)
            nexttrigger = datetime.now() + timedelta(seconds=5)
            self._log_error("_open_blinds_cooldown: Catched Error. Restart in %s" %
                        nexttrigger,prefix=entityid)
            self._set_handle(entityid, "obcd_handle", self.run_at(
                self._open_blinds_cooldown, datetime.now() + timedelta(seconds=5), entityid=entityid))
        finally:
            self._lock.release()

    def _log(self, msg, prefix=None):
        curframe = inspect.currentframe()
        calframe = inspect.getouterframes(curframe, 2)
        callername = calframe[1][3]
        if prefix is not None and prefix!="":
            self.log("%s: %s: %s: %s" % (self.__class__.__name__, prefix,callername, msg))
        else:
            self.log("%s: %s: %s" % (self.__class__.__name__, callername, msg))

    def _log_debug(self, msg, prefix=None):
        curframe = inspect.currentframe()
        calframe = inspect.getouterframes(curframe, 2)
        callername = calframe[1][3]
        if self.args["debug"]:
            if prefix is not None and prefix!="":
                self.log("DEBUG: %s: %s: %s: %s" % (self.__class__.__name__, prefix,callername, msg))
            else:
                self.log("DEBUG: %s: %s: %s" % (self.__class__.__name__, callername, msg))

    def _log_error(self, msg, prefix=None):
        curframe = inspect.currentframe()
        calframe = inspect.getouterframes(curframe, 2)
        callername = calframe[1][3]
        if prefix is not None and prefix!="":
            self.log("%s: %s: %s: %s" % (self.__class__.__name__, prefix, callername, msg))
        else:
            self.log("%s: %s: %s" % (self.__class__.__name__, callername, msg))

    def _convertname(self, name):
        if name is not None and name != "":
            return name.lower().replace(" ", "_")
        else:
            return None

    def _getid(self, statedict, entity):
        idlist = ['friendly_name', 'id', 'value_id']
        count = 0
        id = None
        while id is None and count < len(idlist):
            self._log_debug("idlist: %s" % idlist[count])
            id = self._convertname(self._getattribute(
                statedict, entity, idlist[count]))
            count += 1
        if id is None:
            # id is still None. We have to clarify where to get the id
            self._log_debug("Could not detect id of the item. Values %s" %
                self.statetict.get(entity))
        return id

    def _getattribute(self, statedict, entity, atr):
        self._log_debug(statedict.get(entity).get("attributes"))
        return statedict.get(entity).get("attributes").get(atr, None)


class GlobalBlindsControl(hass.Hass):

    def initialize(self):
        # listen for config changes
        self._lock = Semaphore(1)
        self._ob_handle = self.listen_state(
            self._open_blinds, "input_boolean.control_blinds_open_all_blinds_global", duration=1)
        self._cb_handle = self.listen_state(
            self._close_blinds, "input_boolean.control_blinds_close_all_blinds_global", duration=1)

    def _open_blinds(self, entity, attribute, old, new, duration):
        try:
            self._lock.acquire(True)
            if new == "on":
                self._log("Opening all blinds!")
                self.call_service("cover/open_cover")
                self.call_service("input_boolean/turn_off",
                                  entity_id="input_boolean.control_blinds_open_all_blinds_global")
        except:
            self._log_error(traceback.format_exc())
        finally:
            self._lock.release()

    def _close_blinds(self, entity, attribute, old, new, duration):
        self._lock.acquire(True)
        try:
            if new == "on":
                self._log("Closing all blinds!")
                self.call_service("cover/close_cover")
                self.call_service("input_boolean/turn_off",
                                  entity_id="input_boolean.control_blinds_close_all_blinds_global")
        except:
            pass
        finally:
            self._lock.release()

    def _log(self, msg, prefix=None):
        curframe = inspect.currentframe()
        calframe = inspect.getouterframes(curframe, 2)
        callername = calframe[1][3]
        if prefix is not None and prefix!="":
            self.log("%s: %s: %s: %s" % (self.__class__.__name__, prefix, callername, msg))
        else:
            self.log("%s: %s: %s" % (self.__class__.__name__, callername, msg))

    def _log_debug(self, msg, prefix=None):
        curframe = inspect.currentframe()
        calframe = inspect.getouterframes(curframe, 2)
        callername = calframe[1][3]
        if self.args["debug"]:
            if prefix is not None and prefix!="":
                self.log("DEBUG: %s: %s: %s: %s" % (self.__class__.__name__, prefix, callername, msg))
            else:
                self.log("DEBUG: %s: %s: %s" % (self.__class__.__name__, callername, msg))

    def _log_error(self, msg, prefix=None):
        curframe = inspect.currentframe()
        calframe = inspect.getouterframes(curframe, 2)
        callername = calframe[1][3]
        if prefix is not None and prefix!="":
            self.log("%s: %s: %s: %s" % (self.__class__.__name__, prefix, callername, msg))
        else:
            self.log("%s: %s: %s" % (self.__class__.__name__, callername, msg))


class BlindsControlConfiguration(hass.Hass):
    variables_boolean = {"use_pd_on_close": {"name": "Only close blinds automatically if nobody is home", "icon": "mdi:account-multiple"},
                         "openblinds": {"name": "Open blinds automatically", "icon": "mdi:blinds"},
                         "closeblinds": {"name": "Close blinds automatically", "icon": "mdi:blinds"},
                         "cooldown_during_night": {"name": "Openblinds during night to cool down", "icon": "mdi:weather-night"},
                         "sunsetsunrise": {"name": "Control blinds according to sunrise/sunset", "icon": "mdi:white-balance-sunny"},
                         }
    variables_datetime = {"offset_blinds_up_weekend": {"name": "Offset for open blinds at Weekends", "icon": "mdi:timelapse", "has_date": False, "has_time": True},
                          "cooldown_during_night_open": {"name": "Time to open blinds during night for cool down", "icon": "mdi:clock-outline", "has_date": False, "has_time": True},
                          "cooldown_during_night_close": {"name": "Time to close blinds during night for cool down", "icon": "mdi:clock-outline", "has_date": False, "has_time": True},
                          "earliest_time_blinds_up": {"name": "Earliest time to open blinds. Delay if sunrise is before this time.", "icon": "mdi:clock-outline", "has_date": False, "has_time": True},
                          "latest_time_blinds_down": {"name": "Latest time to close blinds. Move close blinds to this time if sunset is after this time.", "icon": "mdi:clock-outline", "has_date": False, "has_time": True},
                          "offset_blinds_down_after_sunset": {"name": "Offset to add to sunset time.", "icon": "mdi:clock-outline", "has_date": False, "has_time": True},
                          "openblinds_on_time": {"name": "Time to open blinds", "icon": "mdi:clock-outline", "has_date": False, "has_time": True},
                          "closeblinds_on_time": {"name": "Time to close blinds", "icon": "mdi:clock-outline", "has_date": False, "has_time": True}
                          }
    variables_number = {"cooldown_night_blinds_position": {
        "name": "Position of blinds during cool down", "min": 0, "max": 100, "step": 1, "icon": "mdi:blinds"}}
    variables_boolean_global = {"enable_global": {"name": "Enable automatic blinds control", "icon": "mdi:blinds"},
                                "enable_pd_global": {"name": "Control blinds only if nobody is home", "icon": "mdi:account-multiple"},
                                "enable_cooldown_during_night_global": {"name": "Openblinds during night to cool down", "icon": "mdi:weather-night"},
                                "open_all_blinds_global": {"name": "Open ALL blinds", "icon": "mdi:blinds"},
                                "close_all_blinds_global": {"name": "Close ALL blinds", "icon": "mdi:blinds"},
                                "configuration": {"name": "Create new config templates"}
                                }

    def initialize(self):
        self._lock = Semaphore(1)
        self.cfg_handle = self.listen_state(
            self.update_config_files, "input_boolean.control_blinds_configuration", duration=10)

        if self.get_state("input_boolean.control_blinds_configuration") is None:
            # variable does not exit, config is created for the first time
            # start config creation
            if self.args["debug"]:
                self._log("input_boolean.control_blinds_configuration is None")
            self.create_config_files()
        else:
            if self.args["debug"]:
                self._log(
                    "input_boolean.control_blinds_configuration is not None")

    def update_config_files(self, entity, attribute, old, new, duration):
        if new:
            # deactivate boolean
            self.call_service("input_boolean/turn_off",
                              entity_id="input_boolean.control_blinds_configuration")
            # run config creation
            self.create_config_files()

    def create_config_files(self):
        self._log("create_config_files")
        statedict = self.get_state()
        overwritefiles = True
        idlist = list()
        for entity in statedict:
            if re.match('^cover.*', entity, re.IGNORECASE):
                # detected cover
                id = self._getid(statedict, entity)
                idlist.append(id)
                # create all required variables
                # Name convention: <type>.control_blinds_<id>_<variable>
                # Example Friendly_name
                # input_boolean.control_blinds_<id>_use_pd_on_close
                # input_boolean.control_blinds_<id>_openblinds
                # input_boolean.control_blinds_<id>_closeblinds
                # input_boolean.control_blinds_<id>_cooldown_during_night
                # input_boolean.control_blinds_<id>_sunsetsunrise
                # input_datetime.control_blinds_<id>_offset_blinds_up_weekend
                # input_datetime.control_blinds_<id>_cooldown_during_night_open
                # input_datetime.control_blinds_<id>_cooldown_during_night_close
                # input_datetime.control_blinds_<id>_earliest_time_blinds_up
                # input_datetime.control_blinds_<id>_latest_time_blinds_down
                # input_datetime.control_blinds_<id>_offset_blinds_down_after_sunset
                # input_datetime.control_blinds_<id>_openblinds
                # input_datetime.control_blinds_<id>_closeblinds
                # input_number.control_blinds_<id>_cooldown_night_blinds_position

                # create boolean variabels
                self._writevariables(id, "input_boolean",
                                     self.variables_boolean, overwritefiles)
                self._writevariables(id, "input_datetime",
                                     self.variables_datetime, overwritefiles)
                self._writevariables(id, "input_number",
                                     self.variables_number, overwritefiles)
                self._writeconfiguration(id, {"input_boolean": self.variables_boolean,
                                              "input_datetime": self.variables_datetime, "input_number": self.variables_number}, overwritefiles)
                overwritefiles = False
            else:
                if self.args["debug"]:
                    self._log("Entity %s does not match." % entity)

        # add global variables
        # input_boolean.control_blinds_enable_global
        # input_boolean.control_blinds_enable_pd_global
        # input_boolean.control_blinds_enable_cooldown_during_night_global
        # input_boolean.control_blinds_open_all_blinds_global
        # input_boolean.control_blinds_close_all_blinds_global

        self._writevariables("global", "input_boolean",
                             self.variables_boolean_global, False)
        self._writeconfiguration(
            "global", {"input_boolean": self.variables_boolean_global}, False)
        idlist.append("config_blinds_")
        self._writeconfigview(idlist, False)

    def _writevariables(self, id, filename, varlist, overwritefiles):
        if id is None:
            id = ""
        # Create Storage path
        path = os.path.abspath(__file__)
        dir_path = os.path.dirname(path)
        fileout = open("%s%s%s.yaml_" % (dir_path, os.sep,
                                         filename), "w" if overwritefiles else "a")
        fileout.write("##Start## %s\n" % id)
        for v in varlist:
            if id != "" and id != "global":
                fileout.write("control_blinds_%s_%s:\n" % (id, v))
            else:
                fileout.write("control_blinds_%s:\n" % v)
            elem = varlist.get(v)
            for e in elem:
                fileout.write("  %s: %s\n" % (e, elem.get(e)))
        fileout.write("##End## %s\n\n" % id)
        fileout.close()

    def _writeconfiguration(self, id, vardict, overwritefiles):
        if id is None:
            id = ""
        # Create Storage path
        path = os.path.abspath(__file__)
        dir_path = os.path.dirname(path)
        fileout = open("%s%sconfig_blinds.yaml_" %
                       (dir_path, os.sep), "w" if overwritefiles else "a")
        fileout.write("##Start## %s\n" % id)
        fileout.write("config_blinds_%s:\n" % id)
        fileout.write("  name: Config Blinds %s\n" % id)
        fileout.write("  view: no\n")
        fileout.write("  entities:\n")
        for k in vardict:
            varlist = vardict.get(k)
            for v in varlist:
                if id != "" and id != "global":
                    fileout.write(
                        "    - %s.control_blinds_%s_%s\n" % (k, id, v))
                else:
                    fileout.write("    - %s.control_blinds_%s\n" % (k, v))
        fileout.write("##End## %s\n\n" % id)
        fileout.close()

    def _writeconfigview(self, idlist, overwritefiles):
        # Create Storage path
        path = os.path.abspath(__file__)
        dir_path = os.path.dirname(path)
        fileout = open("%s%sconfig_blinds.yaml_" %
                       (dir_path, os.sep), "w" if overwritefiles else "a")
        fileout.write("##Start## config_blinds\n")
        fileout.write("config_blinds:\n")
        fileout.write("  name: Config Blinds\n")
        fileout.write("  view: yes\n")
        fileout.write("  entities:\n")
        for id in idlist:
            fileout.write("    - group.config_blinds_%s\n" % id)
        fileout.write("##End## config_blinds\n\n")
        fileout.close()

    def _getattribute(self, statedict, entity, atr):
        return statedict.get(entity).get("attributes").get(atr, None)

    def _log(self, msg, prefix=None):
        curframe = inspect.currentframe()
        calframe = inspect.getouterframes(curframe, 2)
        callername = calframe[1][3]
        if prefix is not None and prefix!="":
            self.log("%s: %s: %s: %s" % (self.__class__.__name__, prefix, callername, msg))
        else:
            self.log("%s: %s: %s" % (self.__class__.__name__, callername, msg))

    def _log_debug(self, msg, prefix=None):
        curframe = inspect.currentframe()
        calframe = inspect.getouterframes(curframe, 2)
        callername = calframe[1][3]
        if self.args["debug"]:
            if prefix is not None and prefix!="":
                self.log("DEBUG: %s: %s: %s: %s" % (self.__class__.__name__, prefix, callername, msg))
            else:
                self.log("DEBUG: %s: %s: %s" % (self.__class__.__name__, callername, msg))

    def _log_error(self, msg, prefix=None):
        curframe = inspect.currentframe()
        calframe = inspect.getouterframes(curframe, 2)
        callername = calframe[1][3]
        if prefix is not None and prefix!="":
            self.log("%s: %s: %s: %s" % (self.__class__.__name__, prefix, callername, msg))
        else:
            self.log("%s: %s: %s" % (self.__class__.__name__, callername, msg))

    def _convertname(self, name):
        if name is not None and name != "":
            return name.lower().replace(" ", "_")
        else:
            return None

    def _getid(self, statedict, entity):
        idlist = ['friendly_name', 'id', 'value_id']
        count = 0
        id = None
        while id is None and count < len(idlist):
            id = self._convertname(self._getattribute(
                statedict, entity, idlist[count]))
            count += 1
        if id is None:
            # id is still None. We have to clarify where to get the id
            self._log_debug(
                "Could not detect id of the item. Values %s" % self.statetict.get(entity))
        return id
