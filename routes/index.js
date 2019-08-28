const express = require('express');
const request = require('request')
const router = express.Router();
const _ = require("lodash")

router.get('/', (req, res) => {
  res.render('form', { title: 'Registration form' });
  router.post('/', (reqRouter, resRouter) => {
    request(reqRouter.body["soakLog"], { json: true }, (err, res, body) => {
      function eventsToJSONSchedule(json, startTime=null, endTime=null){
        var schedule = {}
        if(typeof json === 'object' && json !== null){
          channels = json.full_list.channels
          for (channel in channels){
            for(eventChannel in channels[channel].events){
              eventToSort = channels[channel].events[eventChannel]
              channels[channel].events[eventChannel]['failed'] = json.failed_list.some(function(el) {
                return el.event.eventLocator === eventToSort.eventLocator;
              });
              if(!channels[channel].events[eventChannel]['failed']){
                channels[channel].events[eventChannel]['acquired'] = json.list.events.some(function(el) {
                  return (el.eventLocator === eventToSort.eventLocator);
                });
              }else{
                channels[channel].events[eventChannel]['acquired'] = false
              }
              if(typeof(schedule[eventToSort.startTime]) === "undefined"){
                schedule[eventToSort.startTime] = [];
              }
              schedule[eventToSort.startTime].push(eventToSort);
            }
          }
          var timeToSend = []
          var schedule_channels = {}
          var rawEvents = []
          for(channel in channels){
            schedule_channels[channels[channel].service] = []
            for(time in schedule){
              if (startTime !== null && endTime !== null){
                if(parseInt(time)>=startTime && parseInt(time)<=endTime){
                  timeToSend.push(time)
                  event_with_time = function(array, start){
                    for(i in array){
                      if(array[i].startTime == start){
                        return array[i]
                      }
                    }
                    return ""
                  }
                  eventToAddToSchedule = event_with_time(channels[channel].events, time)
                  schedule_channels[channels[channel].service].push(eventToAddToSchedule);
                  if(eventToAddToSchedule!=""){
                    rawEvents.push(eventToAddToSchedule)
                  }
                }
              }else{
                timeToSend.push(time)
                event_with_time = function(array, start){
                  for(i in array){
                    if(array[i].startTime == start){
                      return array[i]
                    }
                  }
                  return ""
                }
                eventToAddToSchedule = event_with_time(channels[channel].events, time)
                schedule_channels[channels[channel].service].push(eventToAddToSchedule);
                if(eventToAddToSchedule!=""){
                  rawEvents.push(eventToAddToSchedule)
                }
              }
            }
          }
          var finalParsedSchedules = []
          for(channel in schedule_channels){
            finalParsedSchedules.push({
              channel:channel,
              events:schedule_channels[channel]
            })
          }
          finalParsedSchedules.times = timeToSend.filter(function(elem, pos) {
            return timeToSend.indexOf(elem) == pos;
          }).sort()
          //console.log(finalParsedSchedules)
          finalParsedSchedules.list = rawEvents
          return finalParsedSchedules
        }
        return {}
      }
      var getEventsFromLocator = function(eventLocators, json){
        listEvents = []
        if(json.length==1){
          channels = json.full_list.channels
          for (channel in channels){
            for(eventChannel in channels[channel].events){
              eventToSort = channels[channel].events[eventChannel]
              for(eventLocator in eventLocators){
                event = eventLocators[eventLocator]
                if(eventToSort.eventLocator == event){
                  listEvents.push(eventToSort)
                }
              }
            }
          }
        }
        return listEvents
      }
      if (err) {
        resRouter.render('form', { title: 'NO' });
      }else{
        var _body = body
        if('_source' in body){
          if('data' in body["_source"]){
            body = body["_source"]["data"]
            body["blocks"] = JSON.parse(body["blocks"])
            var jsonParsed = eventsToJSONSchedule(body)
            resRouter.render('form', {
              title: 'YES',
              soak : body,
              time : jsonParsed
            })
            router.get('/editor', (reqRouter, resRouter) => {
              resRouter.render('editor', {
                title: 'YES',
                soak : body,
                time : jsonParsed
              });
              router.post('/downloadEditorResults', (reqRouter, resRouter) => {
                eventsList = getEventsFromLocator(reqRouter.body.eventLocators, body)
                var data = eventsList
                var temp_body = _body
                temp_body["list"] = data
                request.post('https://testaut-elk-1.dev.youview.co.uk/elasticsearch/slot_store/data/dvr-soak-rollback', {
                  json: temp_body
                }, (error, resPost, bodyPost) => {
                  resRouter.send({ statusCode: res.statusCode, error : error });
                });
              });
            });
            router.post('/shortenTimes', (reqRouter, resRouter) => {
              jsonParsed = eventsToJSONSchedule(body, parseInt(reqRouter.body.startTime), parseInt(reqRouter.body.endTime))
              resRouter.render('form', {
                title: 'YES',
                soak : body,
                time : jsonParsed
              });
              router.get('/saveCloud', function (req, res) {
                var data = JSON.stringify(jsonParsed.list);
                var temp_body = _body
                temp_body["list"] = data
                request.post('https://testaut-elk-1.dev.youview.co.uk/elasticsearch/slot_store/data/dvr-soak-rollback', {
                  json: temp_body
                }, (error, resPost, bodyPost) => {
                  res.send({ statusCode: res.statusCode, error : error });
                });
              });
            });
          }else{
            resRouter.render('form', { title: 'dvr-soak' });
          }
        }else{
          resRouter.render('form', { title: 'dvr-soak' });
        }
      }
    });
  });
});
module.exports = router;
